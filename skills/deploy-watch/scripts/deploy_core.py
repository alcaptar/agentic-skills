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

`Estado`, `Veredicto` y `Modo` son `StrEnum` y no constantes sueltas: son conjuntos
cerrados que viajan en el JSON de entrada y de salida, asi que el miembro se serializa
como su cadena -el contrato con quien invoca no cambia- pero la firma dice cual de los
valores es, y un estado inventado no compila en vez de colarse como `str`.

Uso como CLI (JSON in/out, para que el agente lo invoque sin parsear prosa):
    deploy_core.py verdict < payload.json
donde payload.json = {"config": {...}, "baseline_samples": [...], "tick_history": [...],
                      "elapsed_secs": N}

Exit codes: 0 = veredicto emitido en stdout (el veredicto va DENTRO del JSON, no en el codigo),
2 = error de uso -subcomando desconocido o `config` con claves o valores que este modulo no
conoce-. La config no se valida por pulcritud: la escribe el agente a partir de la prosa de la
skill, y una clave mal escrita que se ignorase en silencio degradaria una senal declarada a
inferida (o dejaria el monitor sin senales), o sea el `go` generico que este modulo existe para
no dar.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field, fields
from enum import StrEnum


class Estado(StrEnum):
    """Estado de una muestra puntual frente a los umbrales de su senal."""

    OK = "ok"
    WARN = "warn"
    BREACH = "breach"


class Veredicto(StrEnum):
    """Veredicto del monitor sobre el deploy."""

    GO = "go"
    NO_GO = "no-go"
    INCONCLUSIVE = "inconclusive"


class Modo(StrEnum):
    """Como se calculan los umbrales de una senal.

    `RELATIVO` los deriva del baseline (`mean + N*sigma`); `ABSOLUTO` usa los fijos que declare
    la config. Era un `str` libre, y un `mode: "relatve"` caia en la rama absoluta con
    `warn_abs=crit_abs=0.0`, o sea toda muestra en breach: el falso no-go simetrico del `go`
    generico que el resto del modulo evita.
    """

    RELATIVO = "relative"
    ABSOLUTO = "absolute"


@dataclass(frozen=True, kw_only=True, slots=True)
class SignalConfig:
    """Config de una senal.

    `critical`: su breach confirmado fuerza no-go. `inverted`: True si los valores BAJOS son
    los malos (p. ej. `ready`). `declarada`: True si la senal viene declarada en la spec (la
    linea `SENAL:` del issue) en vez de inferida por blast radius; una declarada que no se
    puede medir NO puede dar `go`, porque seria devolver el veredicto generico por la puerta
    de atras.
    """

    critical: bool = True
    mode: Modo = Modo.RELATIVO
    warn_sigma: float = 2.0
    crit_sigma: float = 3.0
    warn_abs: float = 0.0
    crit_abs: float = 0.0
    inverted: bool = False
    declarada: bool = False

    @staticmethod
    def from_dict(d: dict[str, object]) -> SignalConfig:
        """Config de una senal desde el payload. Una clave o un valor que no cuadran son error.

        Antes se ignoraba en silencio, y esa es la unica ruta por la que la config entra de
        verdad: la escribe el agente a partir de la prosa de la skill, no un fichero versionado.
        Un `declarado: true` mal escrito volvia a `declarada=False` sin decir nada, o sea la
        senal que la slice prometio degradada a inferida, y con ella el `go` generico que ese
        campo existe para impedir -justo el fallo silencioso que la skill describe-. Fail-closed
        como el resto del repo: sin config que se pueda avalar no se emite veredicto.

        El tipo del valor se comprueba por el mismo motivo que el nombre de la clave. Antes se
        asignaba crudo, asi que un `"critical": "no"` quedaba en un `str` que toda condicion lee
        como verdadero, y un `"crit_abs": "5"` no reventaba aqui sino ticks despues, al comparar
        una muestra contra una cadena.
        """
        desconocidas = sorted(set(d) - _CLAVES_SENAL)
        if desconocidas:
            raise ValueError(f"claves de senal desconocidas: {', '.join(desconocidas)}")

        base = SignalConfig()
        return SignalConfig(
            critical=_bool(d, "critical", base.critical),
            mode=_modo(d, "mode", base.mode),
            warn_sigma=_numero(d, "warn_sigma", base.warn_sigma),
            crit_sigma=_numero(d, "crit_sigma", base.crit_sigma),
            warn_abs=_numero(d, "warn_abs", base.warn_abs),
            crit_abs=_numero(d, "crit_abs", base.crit_abs),
            inverted=_bool(d, "inverted", base.inverted),
            declarada=_bool(d, "declarada", base.declarada),
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class MonitorConfig:
    """Ventanas y senales del monitor.

    `failure_limit`: ticks seguidos en breach para confirmarlo. `warmup_secs`: grace tras el
    cambio, donde los breaches se ven pero no cuentan. `min_observe_secs`: no se declara `go`
    antes de cubrir esta ventana. `noisy_cv`: coeficiente de variacion del baseline por encima
    del cual se avisa de que el delta no es de fiar.
    """

    signals: dict[str, SignalConfig] = field(default_factory=dict)
    failure_limit: int = 2
    warmup_secs: int = 60
    min_observe_secs: int = 300
    noisy_cv: float = 0.5

    @staticmethod
    def from_dict(d: dict[str, object]) -> MonitorConfig:
        """Config del monitor desde el payload, con el mismo fail-closed que las senales.

        `signals` con otra forma tambien pasaba en silencio, y su consecuencia es la peor de
        todas: cero senales configuradas, ninguna en breach, `go` sobre un deploy que nadie
        miro.
        """
        desconocidas = sorted(set(d) - _CLAVES_MONITOR)
        if desconocidas:
            raise ValueError(f"claves de config desconocidas: {', '.join(desconocidas)}")

        signals = d.get("signals", {})
        if not isinstance(signals, dict):
            raise TypeError(f"`signals` tiene que ser un objeto, no {type(signals).__name__}")

        base = MonitorConfig()
        return MonitorConfig(
            signals={str(k): SignalConfig.from_dict(_objeto(v, f"signals.{k}")) for k, v in signals.items()},
            failure_limit=_entero(d, "failure_limit", base.failure_limit),
            warmup_secs=_entero(d, "warmup_secs", base.warmup_secs),
            min_observe_secs=_entero(d, "min_observe_secs", base.min_observe_secs),
            noisy_cv=_numero(d, "noisy_cv", base.noisy_cv),
        )


_CLAVES_SENAL = frozenset(f.name for f in fields(SignalConfig))
_CLAVES_MONITOR = frozenset(f.name for f in fields(MonitorConfig))
"""Claves aceptadas por cada `from_dict`, derivadas de los propios dataclasses.

Una lista escrita a mano en paralelo es la forma de que un campo nuevo quede rechazado como
"desconocido" por haberse olvidado de anadirlo en dos sitios.
"""


def _bool(d: dict[str, object], clave: str, default: bool) -> bool:
    valor = d.get(clave, default)
    if not isinstance(valor, bool):
        raise TypeError(f"`{clave}` tiene que ser true o false, no {type(valor).__name__}")
    return valor


def _numero(d: dict[str, object], clave: str, default: float) -> float:
    """El valor como float. `bool` se rechaza aparte: sin eso, un `warn_abs: true` pasaria como 1.0."""
    valor = d.get(clave, default)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise TypeError(f"`{clave}` tiene que ser un numero, no {type(valor).__name__}")
    return float(valor)


def _entero(d: dict[str, object], clave: str, default: int) -> int:
    valor = _numero(d, clave, default)
    if valor != int(valor):
        raise ValueError(f"`{clave}` tiene que ser un entero de segundos o ticks, no {valor}")
    return int(valor)


def _modo(d: dict[str, object], clave: str, default: Modo) -> Modo:
    valor = d.get(clave, default)
    if isinstance(valor, str):
        try:
            return Modo(valor)
        except ValueError as exc:
            raise ValueError(f"`{clave}` invalido: {valor!r} (validos: {', '.join(Modo)})") from exc
    raise TypeError(f"`{clave}` tiene que ser una cadena, no {type(valor).__name__}")


def _objeto(valor: object, donde: str) -> dict[str, object]:
    if not isinstance(valor, dict):
        raise TypeError(f"`{donde}` tiene que ser un objeto, no {type(valor).__name__}")
    return {str(k): v for k, v in valor.items()}


@dataclass(frozen=True, kw_only=True, slots=True)
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
    return [
        f"baseline ruidoso en '{sig}' (cv={b.std / b.mean:.2f} > {noisy_cv}): "
        f"sube baseline_secs o no te fies del delta de esta senal"
        for sig, b in base.items()
        if b.mean > 0 and (b.std / b.mean) > noisy_cv
    ]


def _thresholds(base: Baseline | None, cfg: SignalConfig) -> tuple[float, float]:
    """Los (warn, crit) efectivos de una senal.

    Relativo solo si hay baseline con dispersion util; si el baseline es ~0 (tipico de
    errores) no hay sigma que valga, asi que se cae a los absolutos.
    """
    if cfg.mode is Modo.RELATIVO and base is not None and (base.mean > 0 or base.std > 0):
        return (base.mean + cfg.warn_sigma * base.std, base.mean + cfg.crit_sigma * base.std)
    return (cfg.warn_abs, cfg.crit_abs)


def classify(value: float, base: Baseline | None, cfg: SignalConfig) -> Estado:
    """Estado de una muestra puntual: ok | warn | breach.

    Con `inverted`, los valores bajos son los malos (p. ej. `ready`): warn y crit son minimos
    aceptables y el breach es caer POR DEBAJO del critico, asi que el propio umbral aun es OK.
    """
    warn_v, crit_v = _thresholds(base, cfg)
    if cfg.inverted:
        if value < crit_v:
            return Estado.BREACH
        if value < warn_v:
            return Estado.WARN
        return Estado.OK
    if value >= crit_v:
        return Estado.BREACH
    if value >= warn_v:
        return Estado.WARN
    return Estado.OK


def _sustained(states: list[Estado], failure_limit: int) -> bool:
    """True si los ultimos `failure_limit` estados son BREACH (breach confirmado)."""
    if failure_limit <= 0 or len(states) < failure_limit:
        return False
    return all(s is Estado.BREACH for s in states[-failure_limit:])


@dataclass(frozen=True, kw_only=True, slots=True)
class SignalScore:
    """Lo que se sabe de una senal tras la ventana de observacion.

    `measured` es False cuando no llego ninguna muestra: sin muestras no hay `worst` real, y
    `ok` ahi significa "no medido". Distinguirlo es lo que impide que una senal ilegible pase
    por sana.

    Era un `dict[str, object]` y sus consumidores lo leian con `.get("critical")`, asi que una
    clave mal escrita en el productor y una ausente en el consumidor daban lo mismo: `None`, que
    en `verdict` se lee como "ni critica ni confirmada" y no bloquea nada. Con campos, la senal
    sin medir tiene un default declarado y el typo no compila.
    """

    worst: Estado
    breaches: int
    confirmed: bool
    critical: bool
    measured: bool
    declarada: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "worst": str(self.worst),
            "breaches": self.breaches,
            "confirmed": self.confirmed,
            "critical": self.critical,
            "measured": self.measured,
            "declarada": self.declarada,
        }


def build_scorecard(
    tick_history: list[dict[str, float]],
    baseline: dict[str, Baseline],
    config: MonitorConfig,
) -> dict[str, SignalScore]:
    """Por senal: peor estado, nº de breaches y si el breach esta confirmado (sostenido)."""
    card: dict[str, SignalScore] = {}
    orden = {Estado.OK: 0, Estado.WARN: 1, Estado.BREACH: 2}
    signals = config.signals or {k: SignalConfig() for k in (tick_history[0] if tick_history else {})}
    for sig, cfg in signals.items():
        states = [classify(float(t[sig]), baseline.get(sig), cfg) for t in tick_history if sig in t]
        card[sig] = SignalScore(
            worst=max(states, key=lambda s: orden[s]) if states else Estado.OK,
            breaches=sum(1 for s in states if s is Estado.BREACH),
            confirmed=_sustained(states, config.failure_limit),
            critical=cfg.critical,
            measured=bool(states),
            declarada=cfg.declarada,
        )
    return card


@dataclass(frozen=True, kw_only=True, slots=True)
class Dictamen:
    """El veredicto del monitor y las senales que lo sostienen.

    Las claves que emite `to_dict` son las que consume la prosa de la skill y no cambian con
    el nombre de los campos: son contrato, no nombres internos.
    """

    veredicto: Veredicto
    razon: str
    bloqueantes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {"verdict": str(self.veredicto), "reason": self.razon, "blocking": self.bloqueantes}


def verdict(scorecard: dict[str, SignalScore], config: MonitorConfig, elapsed_secs: float) -> Dictamen:
    """go / no-go / inconclusive a partir del scorecard y las ventanas de tiempo.

    El orden de las ramas es la decision: dentro del warm-up los breaches se ven pero no
    deciden todavia. Despues manda el breach critico sostenido. Solo entonces se mira si
    alguna senal declarada en la spec no se pudo medir (serie inexistente, query vacia,
    fuente caida), que no es un `go` sino un fallo de la senal, y hay que decirlo: va detras
    del no-go porque un breach real es informacion mas fuerte que "no se pudo medir".
    """
    if elapsed_secs < config.warmup_secs:
        return Dictamen(veredicto=Veredicto.INCONCLUSIVE, razon="en warm-up")

    bloqueantes = [sig for sig, s in scorecard.items() if s.critical and s.confirmed]
    if bloqueantes:
        return Dictamen(
            veredicto=Veredicto.NO_GO,
            razon="senal critica en breach sostenido",
            bloqueantes=bloqueantes,
        )

    sin_medir = [sig for sig, s in scorecard.items() if s.declarada and not s.measured]
    if sin_medir:
        return Dictamen(
            veredicto=Veredicto.INCONCLUSIVE,
            razon="senal declarada en la spec sin medir",
            bloqueantes=sin_medir,
        )

    if elapsed_secs < config.min_observe_secs:
        return Dictamen(
            veredicto=Veredicto.INCONCLUSIVE,
            razon="sin breach, pero aun sin cubrir min_observe_secs",
        )

    return Dictamen(veredicto=Veredicto.GO, razon="todas las senales criticas estables")


def _muestras(payload: dict[str, object], clave: str) -> list[dict[str, float]]:
    """Una lista de muestras `{senal: valor}` del payload, validada.

    Antes esto era un `cast` a `list[dict[str, float]]`, que no comprueba nada: un
    `tick_history` con una cadena dentro llegaba intacto hasta `float(t[sig])` y reventaba con
    un traceback en vez de con el exit 2 que el CLI promete para un payload mal formado.

    La posicion va en el mensaje porque quien compone el payload es un agente, y "una muestra
    trae texto" sin decir cual no es accionable en una lista de treinta ticks.
    """
    valor = payload.get(clave) or []
    if not isinstance(valor, list):
        raise TypeError(f"`{clave}` tiene que ser una lista, no {type(valor).__name__}")

    muestras: list[dict[str, float]] = []
    for i, item in enumerate(valor):
        donde = f"{clave}[{i}]"
        muestra = _objeto(item, donde)
        try:
            muestras.append({k: _numero(muestra, k, 0.0) for k in muestra})
        except TypeError as exc:
            raise TypeError(f"en {donde}: {exc}") from exc
    return muestras


def _cli_verdict(payload: dict[str, object]) -> dict[str, object]:
    config = MonitorConfig.from_dict(_objeto(payload.get("config") or {}, "config"))
    baseline_samples = _muestras(payload, "baseline_samples")
    tick_history = _muestras(payload, "tick_history")
    elapsed = _numero(payload, "elapsed_secs", 0.0)

    baseline = aggregate_baseline(baseline_samples)
    card = build_scorecard(tick_history, baseline, config)
    return {
        **verdict(card, config, elapsed).to_dict(),
        "scorecard": {sig: score.to_dict() for sig, score in card.items()},
        "baseline_warnings": baseline_quality(baseline_samples, config.noisy_cv),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI del veredicto.

    Una config invalida sale con 2 y sin veredicto: el payload lo compone quien invoca, y
    emitir `inconclusive` aqui haria pasar su propio despiste por un dato del deploy.
    """
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] != "verdict":
        print("uso: deploy_core.py verdict < payload.json", file=sys.stderr)
        return 2
    payload: object = json.load(sys.stdin)
    try:
        resultado = _cli_verdict(_objeto(payload, "payload"))
    except (TypeError, ValueError) as exc:
        print(f"error: config invalida: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(resultado, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
