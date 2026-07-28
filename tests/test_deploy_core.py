"""Tests del core de decision de deploy-watch (deploy_core.py), puros y offline."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import deploy_core as dc
from deploy_core import (
    Baseline,
    MonitorConfig,
    SignalConfig,
    aggregate_baseline,
    baseline_quality,
    build_scorecard,
    classify,
    verdict,
)

_CORE = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "deploy-watch"
    / "scripts"
    / "deploy_core.py"
)


def test_aggregate_baseline_mean_std() -> None:
    base = aggregate_baseline([{"lat": 10.0}, {"lat": 20.0}, {"lat": 30.0}])
    assert base["lat"].mean == 20.0
    assert round(base["lat"].std, 3) == round((200 / 3) ** 0.5, 3)  # var poblacional


def test_baseline_quality_avisa_de_ruido() -> None:
    # cv alto -> aviso
    warns = baseline_quality([{"x": 1.0}, {"x": 9.0}], noisy_cv=0.5)
    assert warns and "ruidoso" in warns[0]
    # baseline estable -> sin aviso
    assert baseline_quality([{"x": 10.0}, {"x": 10.2}], noisy_cv=0.5) == []


def test_classify_relativo() -> None:
    base = Baseline(mean=100.0, std=10.0)
    cfg = SignalConfig(mode="relative", warn_sigma=2, crit_sigma=3)  # warn=120, crit=130
    assert classify(105, base, cfg) == dc.OK
    assert classify(125, base, cfg) == dc.WARN
    assert classify(140, base, cfg) == dc.BREACH


def test_classify_absoluto_cuando_baseline_cero() -> None:
    base = Baseline(mean=0.0, std=0.0)  # tipico de errores
    cfg = SignalConfig(mode="relative", warn_abs=1, crit_abs=5)
    assert classify(0, base, cfg) == dc.OK
    assert classify(2, base, cfg) == dc.WARN
    assert classify(9, base, cfg) == dc.BREACH


def test_classify_inverted_ready() -> None:
    base = Baseline(mean=1.0, std=0.0)
    cfg = SignalConfig(mode="absolute", warn_abs=1, crit_abs=1, inverted=True)
    assert classify(1, base, cfg) == dc.OK
    assert classify(0, base, cfg) == dc.BREACH


def test_scorecard_confirmacion_sostenida() -> None:
    # un unico breach aislado NO se confirma con failure_limit=2
    cfg = MonitorConfig(
        signals={"e": SignalConfig(mode="absolute", warn_abs=1, crit_abs=5)}, failure_limit=2
    )
    hist_pico = [{"e": 0.0}, {"e": 9.0}, {"e": 0.0}]
    card = build_scorecard(hist_pico, {}, cfg)
    assert card["e"]["breaches"] == 1
    assert card["e"]["confirmed"] is False
    # dos breaches seguidos al final -> confirmado
    hist_sost = [{"e": 0.0}, {"e": 9.0}, {"e": 9.0}]
    card2 = build_scorecard(hist_sost, {}, cfg)
    assert card2["e"]["confirmed"] is True


def test_verdict_warmup_no_decide() -> None:
    cfg = MonitorConfig(warmup_secs=60, min_observe_secs=300)
    card = {"e": {"critical": True, "confirmed": True, "worst": dc.BREACH, "breaches": 3}}
    v = verdict(card, cfg, elapsed_secs=30)
    assert v["verdict"] == dc.INCONCLUSIVE


def test_verdict_no_go_por_critica_confirmada() -> None:
    cfg = MonitorConfig(warmup_secs=60, min_observe_secs=300)
    card = {"e": {"critical": True, "confirmed": True, "worst": dc.BREACH, "breaches": 3}}
    v = verdict(card, cfg, elapsed_secs=120)
    assert v["verdict"] == dc.NO_GO
    assert v["blocking"] == ["e"]


def test_verdict_advisory_no_bloquea() -> None:
    cfg = MonitorConfig(warmup_secs=60, min_observe_secs=100)
    card = {"cpu": {"critical": False, "confirmed": True, "worst": dc.BREACH, "breaches": 5}}
    v = verdict(card, cfg, elapsed_secs=150)
    assert v["verdict"] == dc.GO  # advisory en breach no fuerza no-go


def test_verdict_inconclusive_hasta_min_observe() -> None:
    cfg = MonitorConfig(warmup_secs=60, min_observe_secs=300)
    card = {"e": {"critical": True, "confirmed": False, "worst": dc.OK, "breaches": 0}}
    assert verdict(card, cfg, elapsed_secs=120)["verdict"] == dc.INCONCLUSIVE
    assert verdict(card, cfg, elapsed_secs=400)["verdict"] == dc.GO


def test_scorecard_marca_la_senal_sin_muestras_como_no_medida() -> None:
    cfg = MonitorConfig(
        signals={
            "ajustes": SignalConfig(declarada=True),
            "cpu": SignalConfig(critical=False),
        }
    )

    card = build_scorecard([{"cpu": 10.0}], {}, cfg)

    assert card["ajustes"]["measured"] is False
    assert card["ajustes"]["declarada"] is True
    assert card["cpu"]["measured"] is True


def test_verdict_senal_declarada_sin_medir_no_es_go() -> None:
    # La serie que la spec prometio no existe en prod: el veredicto no puede ser `go`,
    # o el generico ("el servicio esta sano") volveria por la puerta de atras.
    cfg = MonitorConfig(warmup_secs=60, min_observe_secs=100)
    card = {
        "ajustes": {
            "critical": True,
            "confirmed": False,
            "worst": dc.OK,
            "breaches": 0,
            "measured": False,
            "declarada": True,
        },
    }

    v = verdict(card, cfg, elapsed_secs=400)

    assert v["verdict"] == dc.INCONCLUSIVE
    assert v["blocking"] == ["ajustes"]


def test_verdict_senal_inferida_sin_medir_no_frena_el_go() -> None:
    # Solo la declarada en la spec tiene esa fuerza: las inferidas son best-effort.
    cfg = MonitorConfig(warmup_secs=60, min_observe_secs=100)
    card = {
        "cpu": {
            "critical": False,
            "confirmed": False,
            "worst": dc.OK,
            "breaches": 0,
            "measured": False,
            "declarada": False,
        },
    }

    assert verdict(card, cfg, elapsed_secs=400)["verdict"] == dc.GO


def test_verdict_breach_real_manda_sobre_senal_sin_medir() -> None:
    cfg = MonitorConfig(warmup_secs=60, min_observe_secs=100)
    card = {
        "err": {
            "critical": True,
            "confirmed": True,
            "worst": dc.BREACH,
            "breaches": 3,
            "measured": True,
            "declarada": False,
        },
        "ajustes": {
            "critical": True,
            "confirmed": False,
            "worst": dc.OK,
            "breaches": 0,
            "measured": False,
            "declarada": True,
        },
    }

    v = verdict(card, cfg, elapsed_secs=400)

    assert v["verdict"] == dc.NO_GO  # un breach confirmado es informacion mas fuerte
    assert v["blocking"] == ["err"]


def test_cli_verdict_json() -> None:
    payload = {
        "config": {
            "signals": {
                "err": {"critical": True, "mode": "absolute", "warn_abs": 1, "crit_abs": 5}
            },
            "failure_limit": 2,
            "warmup_secs": 0,
            "min_observe_secs": 0,
        },
        "baseline_samples": [{"err": 0.0}, {"err": 0.0}],
        "tick_history": [{"err": 9.0}, {"err": 9.0}],
        "elapsed_secs": 120,
    }
    out = subprocess.run(
        [sys.executable, str(_CORE), "verdict"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(out.stdout)
    assert data["verdict"] == dc.NO_GO
    assert data["blocking"] == ["err"]
    assert data["scorecard"]["err"]["confirmed"] is True
