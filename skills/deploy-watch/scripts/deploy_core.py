#!/usr/bin/env python3
"""Core de decision de deploy-watch (logica pura, patron offload-deterministic).

deploy-watch orquesta la monitorizacion de un deploy: el AGENTE recoge las senales
componiendo las skills de observabilidad (`query-*`) y le pasa las muestras a este
modulo, que decide. Aqui NO hay I/O ni HTTP: solo la logica de decision, testeable
offline con muestras sinteticas.

Que decide (ideas destiladas de Argo Rollouts / Flagger / Kayenta / SRE Workbook,
adaptadas a un monitor ligero):

- Baseline por senal: media + desviacion tipica.
- Umbrales RELATIVOS al baseline (`mean + N*sigma`), no absolutos al aire; absolutos
  solo para senales cuyo baseline es ~0 (p. ej. errores).
- Confirmacion SOSTENIDA: un breach solo cuenta como no-go si persiste `failure_limit`
  ticks seguidos (mata falsos positivos por picos vecinos).
- Senales CRITICAS vs ADVISORY: solo las criticas fuerzan no-go.
- Senales DECLARADAS por la spec (`declarada: true`, la linea `SENAL:` del issue) vs
  inferidas por blast radius: una declarada sin ninguna muestra da `inconclusive`, no
  `go` -si la serie que la spec prometio no existe, el veredicto no puede afirmar que
  el cambio funciona-.
- Veredicto go / no-go / inconclusive, respetando warm-up (grace tras el cambio) y
  min-observe (no declarar `go` hasta cubrir la ventana de rollout+drain).

Uso como CLI (JSON in/out, para que el agente lo invoque sin parsear prosa):
    deploy_core.py verdict < payload.json
donde payload.json = {"config": {...}, "baseline_samples": [...], "tick_history": [...],
                      "elapsed_secs": N}
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from typing import Any, cast

OK = "ok"
WARN = "warn"
BREACH = "breach"

GO = "go"
NO_GO = "no-go"
INCONCLUSIVE = "inconclusive"


@dataclass
class SignalConfig:
    """Config de una senal. `critical` -> su breach confirmado fuerza no-go."""

    critical: bool = True
    mode: str = "relative"  # "relative" (mean+N*sigma) | "absolute" (warn/crit fijos)
    warn_sigma: float = 2.0
    crit_sigma: float = 3.0
    warn_abs: float = 0.0
    crit_abs: float = 0.0
    inverted: bool = False  # True si valores BAJOS son malos (p. ej. ready)
    # True si la senal viene declarada en la spec (linea `SENAL:` del issue) en vez de
    # inferida por blast radius. Una declarada que no se puede medir NO puede dar `go`:
    # seria devolver el veredicto generico por la puerta de atras.
    declarada: bool = False

    @staticmethod
    def from_dict(d: dict[str, object]) -> SignalConfig:
        f = SignalConfig()
        for k, v in d.items():
            if hasattr(f, k):
                setattr(f, k, v)
        return f


@dataclass
class MonitorConfig:
    signals: dict[str, SignalConfig] = field(default_factory=dict)
    failure_limit: int = 2  # ticks seguidos en breach para confirmarlo
    warmup_secs: int = 60  # grace tras el cambio: breaches se ven pero no cuentan
    min_observe_secs: int = 300  # no declarar `go` antes de cubrir esta ventana
    noisy_cv: float = 0.5  # coef. de variacion del baseline por encima del cual se avisa

    @staticmethod
    def from_dict(d: dict[str, object]) -> MonitorConfig:
        cfg = MonitorConfig()
        signals = d.get("signals", {})
        if isinstance(signals, dict):
            cfg.signals = {k: SignalConfig.from_dict(v) for k, v in signals.items()}
        for k in ("failure_limit", "warmup_secs", "min_observe_secs", "noisy_cv"):
            if k in d:
                setattr(cfg, k, d[k])
        return cfg


@dataclass
class Baseline:
    mean: float
    std: float


def aggregate_baseline(samples: list[dict[str, float]]) -> dict[str, Baseline]:
    """Media y desviacion tipica (poblacional) por senal sobre las muestras del baseline."""
    if not samples:
        return {}
    keys = samples[0].keys()
    out: dict[str, Baseline] = {}
    for k in keys:
        vals = [float(s[k]) for s in samples if k in s]
        if not vals:
            continue
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        out[k] = Baseline(mean=mean, std=math.sqrt(var))
    return out


def baseline_quality(samples: list[dict[str, float]], noisy_cv: float) -> list[str]:
    """Avisos de baseline ruidoso: coef. de variacion (std/mean) por encima del umbral."""
    base = aggregate_baseline(samples)
    warnings: list[str] = []
    for sig, b in base.items():
        if b.mean > 0 and (b.std / b.mean) > noisy_cv:
            warnings.append(
                f"baseline ruidoso en '{sig}' (cv={b.std / b.mean:.2f} > {noisy_cv}): "
                f"sube baseline_secs o no te fies del delta de esta senal"
            )
    return warnings


def _thresholds(base: Baseline | None, cfg: SignalConfig) -> tuple[float, float]:
    """Devuelve (warn_v, crit_v) efectivos para una senal."""
    # Relativo solo si hay baseline con dispersion util; si el baseline es ~0
    # (tipico de errores), no hay sigma que valga -> absolutos.
    if cfg.mode == "relative" and base is not None and (base.mean > 0 or base.std > 0):
        return (base.mean + cfg.warn_sigma * base.std, base.mean + cfg.crit_sigma * base.std)
    return (cfg.warn_abs, cfg.crit_abs)


def classify(value: float, base: Baseline | None, cfg: SignalConfig) -> str:
    """Estado de una muestra puntual: ok | warn | breach."""
    warn_v, crit_v = _thresholds(base, cfg)
    if cfg.inverted:
        # Valores bajos son malos (p. ej. ready): warn/crit son minimos aceptables,
        # breach si cae POR DEBAJO del critico (el propio umbral aun es OK).
        if value < crit_v:
            return BREACH
        if value < warn_v:
            return WARN
        return OK
    if value >= crit_v:
        return BREACH
    if value >= warn_v:
        return WARN
    return OK


def _sustained(states: list[str], failure_limit: int) -> bool:
    """True si los ultimos `failure_limit` estados son BREACH (breach confirmado)."""
    if failure_limit <= 0 or len(states) < failure_limit:
        return False
    return all(s == BREACH for s in states[-failure_limit:])


def build_scorecard(
    tick_history: list[dict[str, float]],
    baseline: dict[str, Baseline],
    config: MonitorConfig,
) -> dict[str, dict[str, object]]:
    """Por senal: peor estado, nº de breaches y si el breach esta confirmado (sostenido)."""
    card: dict[str, dict[str, object]] = {}
    order = {OK: 0, WARN: 1, BREACH: 2}
    signals = config.signals or {
        k: SignalConfig() for k in (tick_history[0] if tick_history else {})
    }
    for sig, cfg in signals.items():
        states = [classify(float(t[sig]), baseline.get(sig), cfg) for t in tick_history if sig in t]
        worst = max(states, key=lambda s: order[s]) if states else OK
        card[sig] = {
            "worst": worst,
            "breaches": sum(1 for s in states if s == BREACH),
            "confirmed": _sustained(states, config.failure_limit),
            "critical": cfg.critical,
            # Sin ninguna muestra no hay `worst` real: `ok` ahi significa "no medido", y
            # distinguirlo es lo que impide que una senal ilegible pase por sana.
            "measured": bool(states),
            "declarada": cfg.declarada,
        }
    return card


def verdict(
    scorecard: dict[str, dict[str, object]],
    config: MonitorConfig,
    elapsed_secs: float,
) -> dict[str, object]:
    """go / no-go / inconclusive a partir del scorecard y las ventanas de tiempo."""
    # Dentro del warm-up los breaches se ven pero no deciden todavia.
    if elapsed_secs < config.warmup_secs:
        return {"verdict": INCONCLUSIVE, "reason": "en warm-up", "blocking": []}

    blocking = [sig for sig, s in scorecard.items() if s.get("critical") and s.get("confirmed")]
    if blocking:
        return {
            "verdict": NO_GO,
            "reason": "senal critica en breach sostenido",
            "blocking": blocking,
        }

    # Una senal declarada en la spec que no se pudo medir (serie inexistente, query vacia,
    # fuente caida) no es un `go`: es un fallo de la senal, y hay que decirlo. Va despues del
    # no-go porque un breach real es informacion mas fuerte que "no se pudo medir".
    sin_medir = [
        sig for sig, s in scorecard.items() if s.get("declarada") and not s.get("measured")
    ]
    if sin_medir:
        return {
            "verdict": INCONCLUSIVE,
            "reason": "senal declarada en la spec sin medir",
            "blocking": sin_medir,
        }

    if elapsed_secs < config.min_observe_secs:
        return {
            "verdict": INCONCLUSIVE,
            "reason": "sin breach, pero aun sin cubrir min_observe_secs",
            "blocking": [],
        }

    return {"verdict": GO, "reason": "todas las senales criticas estables", "blocking": []}


def _cli_verdict(payload: dict[str, Any]) -> dict[str, object]:
    config = MonitorConfig.from_dict(payload.get("config") or {})
    baseline_samples = cast("list[dict[str, float]]", payload.get("baseline_samples") or [])
    tick_history = cast("list[dict[str, float]]", payload.get("tick_history") or [])
    elapsed = float(payload.get("elapsed_secs") or 0)

    baseline = aggregate_baseline(baseline_samples)
    card = build_scorecard(tick_history, baseline, config)
    v = verdict(card, config, elapsed)
    return {
        "verdict": v["verdict"],
        "reason": v["reason"],
        "blocking": v["blocking"],
        "scorecard": card,
        "baseline_warnings": baseline_quality(baseline_samples, config.noisy_cv),
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] != "verdict":
        print("uso: deploy_core.py verdict < payload.json", file=sys.stderr)
        return 2
    payload: dict[str, Any] = json.load(sys.stdin)
    print(json.dumps(_cli_verdict(payload), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
