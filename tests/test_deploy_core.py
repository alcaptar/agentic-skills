"""Tests del core de decision de deploy-watch (deploy_core.py), puros y offline."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

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


# --- la config, que es por donde entra de verdad -----------------------------------
#
# Todo lo de arriba construye `MonitorConfig`/`SignalConfig` a mano, y en produccion nadie lo
# hace: el agente compone un payload JSON a partir de la prosa de la skill. Ese tramo -del
# diccionario al dataclass- no tenia ni un test, y es donde una clave mal escrita se convierte
# en un `go` que nadie ha medido.


def test_config_completa_se_lee_del_diccionario() -> None:
    cfg = MonitorConfig.from_dict(
        {
            "signals": {"err": {"critical": True, "mode": "absolute", "crit_abs": 5}},
            "failure_limit": 3,
            "warmup_secs": 30,
        }
    )
    assert cfg.failure_limit == 3
    assert cfg.warmup_secs == 30
    assert cfg.min_observe_secs == 300  # lo que no viene se queda en su default
    assert cfg.signals["err"].mode == "absolute"
    assert cfg.signals["err"].crit_abs == 5


def test_una_clave_de_senal_mal_escrita_no_pasa_en_silencio() -> None:
    # El caso caro: `declarado` en vez de `declarada` degradaba la senal declarada por la slice
    # a inferida sin decir nada, y con ella volvia el `go` generico que ese campo impide.
    with pytest.raises(ValueError, match="declarado"):
        SignalConfig.from_dict({"critical": True, "declarado": True})


def test_una_clave_de_config_mal_escrita_no_pasa_en_silencio() -> None:
    with pytest.raises(ValueError, match="warmup_seconds"):
        MonitorConfig.from_dict({"warmup_seconds": 30})


def test_signals_con_otra_forma_no_deja_el_monitor_ciego() -> None:
    # Sin senales no hay breach posible, asi que esto seria `go` sobre un deploy sin mirar.
    with pytest.raises(TypeError, match="signals"):
        MonitorConfig.from_dict({"signals": ["err", "lat"]})


def test_config_vacia_es_valida_y_da_los_defaults() -> None:
    # No todo lo raro es un error: un payload sin `config` es el caso legitimo de "usa los
    # defaults", y petar ahi dejaria sin veredicto un deploy que se puede juzgar igual.
    cfg = MonitorConfig.from_dict({})
    assert cfg.signals == {}
    assert (cfg.failure_limit, cfg.warmup_secs, cfg.min_observe_secs) == (2, 60, 300)


# --- CLI ---------------------------------------------------------------------------


def _cli(payload: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_CORE), "verdict"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


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
    out = _cli(payload)
    assert out.returncode == 0
    data = json.loads(out.stdout)
    assert data["verdict"] == dc.NO_GO
    assert data["blocking"] == ["err"]
    assert data["scorecard"]["err"]["confirmed"] is True
    assert data["baseline_warnings"] == []  # baseline plano: nada que avisar


def test_cli_emite_el_aviso_de_baseline_ruidoso() -> None:
    # El aviso es la mitad de la salida que decide si fiarse del delta, y hasta ahora ningun
    # test comprobaba que llegue a la salida del CLI (solo que la funcion lo calcula).
    payload = {
        "config": {"signals": {"lat": {}}, "min_observe_secs": 0, "warmup_secs": 0},
        "baseline_samples": [{"lat": 1.0}, {"lat": 9.0}],
        "tick_history": [{"lat": 5.0}],
        "elapsed_secs": 120,
    }
    out = _cli(payload)
    assert out.returncode == 0
    avisos = json.loads(out.stdout)["baseline_warnings"]
    assert len(avisos) == 1
    assert "ruidoso" in avisos[0] and "lat" in avisos[0]


def test_cli_exit_2_y_ningun_veredicto_si_la_config_es_invalida() -> None:
    # Exit 2 = error de uso, como en `controles.py`. Un `inconclusive` aqui haria pasar el
    # despiste de quien invoca por un dato del deploy, que es lo unico peor que no responder.
    out = _cli({"config": {"signals": {"err": {"declarado": True}}}})
    assert out.returncode == 2
    assert out.stdout == ""
    assert "declarado" in out.stderr
