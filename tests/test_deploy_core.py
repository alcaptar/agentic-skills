"""Tests del core de decision de deploy-watch (deploy_core.py), puros y offline."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from deploy_core import (
    Baseline,
    Estado,
    Modo,
    MonitorConfig,
    SignalConfig,
    SignalScore,
    Veredicto,
    aggregate_baseline,
    baseline_quality,
    build_scorecard,
    classify,
    verdict,
)
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import ProcessOutput

_CORE = Path(__file__).resolve().parent.parent / "skills" / "deploy-watch" / "scripts" / "deploy_core.py"


def _score(
    *,
    worst: Estado = Estado.OK,
    breaches: int = 0,
    confirmed: bool = False,
    critical: bool = True,
    measured: bool = True,
    declarada: bool = False,
) -> SignalScore:
    """Una senal ya puntuada, con defaults sanos: cada test nombra solo lo que decide.

    `SignalScore` tiene seis campos y `verdict` mira dos o tres segun la rama. Escribirlos todos
    en cada test enterraba el que estaba bajo prueba entre cinco que daban igual, y era lo que
    hacia comodo pasar dicts a medias, que es como la senal sin medir se colaba como sana.
    """
    return SignalScore(
        worst=worst,
        breaches=breaches,
        confirmed=confirmed,
        critical=critical,
        measured=measured,
        declarada=declarada,
    )


def test_aggregate_baseline_mean_std() -> None:
    """La desviacion es la poblacional, no la de muestra: de ahi el `/3` y no `/2`."""
    base = aggregate_baseline([{"lat": 10.0}, {"lat": 20.0}, {"lat": 30.0}])
    assert base["lat"].mean == 20.0
    assert round(base["lat"].std, 3) == round((200 / 3) ** 0.5, 3)


def test_baseline_quality_avisa_de_ruido() -> None:
    """Un coeficiente de variacion alto avisa; un baseline estable no dice nada."""
    warns = baseline_quality([{"x": 1.0}, {"x": 9.0}], noisy_cv=0.5)
    assert len(warns) == 1
    assert "ruidoso" in warns[0]
    assert baseline_quality([{"x": 10.0}, {"x": 10.2}], noisy_cv=0.5) == []


def test_classify_relativo() -> None:
    """Con baseline mean=100 std=10 y 2/3 sigma, los umbrales efectivos son 120 y 130."""
    base = Baseline(mean=100.0, std=10.0)
    cfg = SignalConfig(mode=Modo.RELATIVO, warn_sigma=2, crit_sigma=3)
    assert classify(105, base, cfg) is Estado.OK
    assert classify(125, base, cfg) is Estado.WARN
    assert classify(140, base, cfg) is Estado.BREACH


def test_classify_absoluto_cuando_baseline_cero() -> None:
    """Baseline plano (el tipico de una senal de errores): no hay sigma, se usan los absolutos."""
    base = Baseline(mean=0.0, std=0.0)
    cfg = SignalConfig(mode=Modo.RELATIVO, warn_abs=1, crit_abs=5)
    assert classify(0, base, cfg) is Estado.OK
    assert classify(2, base, cfg) is Estado.WARN
    assert classify(9, base, cfg) is Estado.BREACH


def test_classify_inverted_ready() -> None:
    base = Baseline(mean=1.0, std=0.0)
    cfg = SignalConfig(mode=Modo.ABSOLUTO, warn_abs=1, crit_abs=1, inverted=True)
    assert classify(1, base, cfg) is Estado.OK
    assert classify(0, base, cfg) is Estado.BREACH


def test_scorecard_confirmacion_sostenida() -> None:
    """Un breach aislado no se confirma con `failure_limit=2`; dos seguidos al final si."""
    cfg = MonitorConfig(signals={"e": SignalConfig(mode=Modo.ABSOLUTO, warn_abs=1, crit_abs=5)}, failure_limit=2)

    card_pico = build_scorecard([{"e": 0.0}, {"e": 9.0}, {"e": 0.0}], {}, cfg)
    assert card_pico["e"].breaches == 1
    assert card_pico["e"].confirmed is False

    card_sostenido = build_scorecard([{"e": 0.0}, {"e": 9.0}, {"e": 9.0}], {}, cfg)
    assert card_sostenido["e"].confirmed is True


def test_verdict_warmup_no_decide() -> None:
    cfg = MonitorConfig(warmup_secs=60, min_observe_secs=300)
    card = {"e": _score(worst=Estado.BREACH, breaches=3, confirmed=True)}
    assert verdict(card, cfg, elapsed_secs=30).veredicto is Veredicto.INCONCLUSIVE


def test_verdict_no_go_por_critica_confirmada() -> None:
    cfg = MonitorConfig(warmup_secs=60, min_observe_secs=300)
    card = {"e": _score(worst=Estado.BREACH, breaches=3, confirmed=True)}

    v = verdict(card, cfg, elapsed_secs=120)

    assert v.veredicto is Veredicto.NO_GO
    assert v.bloqueantes == ["e"]


def test_verdict_advisory_no_bloquea() -> None:
    """Una senal advisory en breach informa, pero no fuerza no-go."""
    cfg = MonitorConfig(warmup_secs=60, min_observe_secs=100)
    card = {"cpu": _score(worst=Estado.BREACH, breaches=5, confirmed=True, critical=False)}

    assert verdict(card, cfg, elapsed_secs=150).veredicto is Veredicto.GO


def test_verdict_inconclusive_hasta_min_observe() -> None:
    cfg = MonitorConfig(warmup_secs=60, min_observe_secs=300)
    card = {"e": _score()}
    assert verdict(card, cfg, elapsed_secs=120).veredicto is Veredicto.INCONCLUSIVE
    assert verdict(card, cfg, elapsed_secs=400).veredicto is Veredicto.GO


def test_scorecard_marca_la_senal_sin_muestras_como_no_medida() -> None:
    cfg = MonitorConfig(
        signals={
            "ajustes": SignalConfig(declarada=True),
            "cpu": SignalConfig(critical=False),
        }
    )

    card = build_scorecard([{"cpu": 10.0}], {}, cfg)

    assert card["ajustes"].measured is False
    assert card["ajustes"].declarada is True
    assert card["cpu"].measured is True


def test_verdict_senal_declarada_sin_medir_no_es_go() -> None:
    """La serie que la spec prometio no existe en prod, asi que el veredicto no puede ser `go`.

    Si lo fuera, el generico -"el servicio esta sano"- volveria por la puerta de atras.
    """
    cfg = MonitorConfig(warmup_secs=60, min_observe_secs=100)
    card = {"ajustes": _score(measured=False, declarada=True)}

    v = verdict(card, cfg, elapsed_secs=400)

    assert v.veredicto is Veredicto.INCONCLUSIVE
    assert v.bloqueantes == ["ajustes"]


def test_verdict_senal_inferida_sin_medir_no_frena_el_go() -> None:
    """Solo la declarada en la spec tiene esa fuerza: las inferidas son best-effort."""
    cfg = MonitorConfig(warmup_secs=60, min_observe_secs=100)
    card = {"cpu": _score(critical=False, measured=False)}

    assert verdict(card, cfg, elapsed_secs=400).veredicto is Veredicto.GO


def test_verdict_breach_real_manda_sobre_senal_sin_medir() -> None:
    """Un breach confirmado es informacion mas fuerte que "no se pudo medir"."""
    cfg = MonitorConfig(warmup_secs=60, min_observe_secs=100)
    card = {
        "err": _score(worst=Estado.BREACH, breaches=3, confirmed=True),
        "ajustes": _score(measured=False, declarada=True),
    }

    v = verdict(card, cfg, elapsed_secs=400)

    assert v.veredicto is Veredicto.NO_GO
    assert v.bloqueantes == ["err"]


def test_config_completa_se_lee_del_diccionario() -> None:
    """El tramo del diccionario al dataclass es por donde entra la config de verdad.

    Todo lo de arriba construye `MonitorConfig`/`SignalConfig` a mano, y en produccion nadie lo
    hace: el agente compone un payload JSON a partir de la prosa de la skill. Ese tramo no tenia
    ni un test, y es donde una clave mal escrita se convierte en un `go` que nadie ha medido.
    """
    cfg = MonitorConfig.from_dict(
        {
            "signals": {"err": {"critical": True, "mode": "absolute", "crit_abs": 5}},
            "failure_limit": 3,
            "warmup_secs": 30,
        }
    )
    assert cfg.failure_limit == 3
    assert cfg.warmup_secs == 30
    assert cfg.min_observe_secs == 300
    assert cfg.signals["err"].mode is Modo.ABSOLUTO
    assert cfg.signals["err"].crit_abs == 5


def test_una_clave_de_senal_mal_escrita_no_pasa_en_silencio() -> None:
    """El caso caro: `declarado` en vez de `declarada`.

    Degradaba la senal declarada por la slice a inferida sin decir nada, y con ella volvia el
    `go` generico que ese campo impide.
    """
    with pytest.raises(ValueError, match="declarado"):
        SignalConfig.from_dict({"critical": True, "declarado": True})


def test_una_clave_de_config_mal_escrita_no_pasa_en_silencio() -> None:
    with pytest.raises(ValueError, match="warmup_seconds"):
        MonitorConfig.from_dict({"warmup_seconds": 30})


def test_signals_con_otra_forma_no_deja_el_monitor_ciego() -> None:
    """Sin senales no hay breach posible, asi que esto seria `go` sobre un deploy sin mirar."""
    with pytest.raises(TypeError, match="signals"):
        MonitorConfig.from_dict({"signals": ["err", "lat"]})


def test_config_vacia_es_valida_y_da_los_defaults() -> None:
    """No todo lo raro es un error: un payload sin `config` es "usa los defaults".

    Petar ahi dejaria sin veredicto un deploy que se puede juzgar igual.
    """
    cfg = MonitorConfig.from_dict({})
    assert cfg.signals == {}
    assert (cfg.failure_limit, cfg.warmup_secs, cfg.min_observe_secs) == (2, 60, 300)


def test_un_mode_que_no_existe_no_cae_en_la_rama_absoluta() -> None:
    """La clave bien escrita con el valor de otro tipo tiene el mismo final que el typo.

    Un `relatve` dejaba la senal en modo absoluto con umbrales `0.0`, o sea TODA muestra en
    breach: el falso no-go simetrico del `go` generico.
    """
    with pytest.raises(ValueError, match="relatve"):
        SignalConfig.from_dict({"mode": "relatve"})


def test_un_critical_que_no_es_booleano_no_pasa_por_verdadero() -> None:
    with pytest.raises(TypeError, match="critical"):
        SignalConfig.from_dict({"critical": "no"})


def test_un_umbral_en_texto_no_llega_hasta_la_comparacion() -> None:
    """Antes no reventaba aqui sino ticks despues, comparando una muestra contra `"5"`."""
    with pytest.raises(TypeError, match="crit_abs"):
        SignalConfig.from_dict({"crit_abs": "5"})


def _cli(payload: object) -> ProcessOutput:
    return Real.process().run([sys.executable, str(_CORE), "verdict"], stdin=json.dumps(payload))


def test_cli_verdict_json() -> None:
    payload = {
        "config": {
            "signals": {"err": {"critical": True, "mode": "absolute", "warn_abs": 1, "crit_abs": 5}},
            "failure_limit": 2,
            "warmup_secs": 0,
            "min_observe_secs": 0,
        },
        "baseline_samples": [{"err": 0.0}, {"err": 0.0}],
        "tick_history": [{"err": 9.0}, {"err": 9.0}],
        "elapsed_secs": 120,
    }
    out = _cli(payload)
    assert out.code == 0
    data = json.loads(out.stdout)
    assert data["verdict"] == Veredicto.NO_GO
    assert data["blocking"] == ["err"]
    assert data["scorecard"]["err"]["confirmed"] is True
    assert data["baseline_warnings"] == []


def test_las_claves_del_json_de_salida_son_las_que_documenta_la_skill() -> None:
    """Los campos del `Dictamen` estan en castellano, pero las claves del JSON son contrato.

    El renombrado no puede filtrarse a la salida, y sin este test el unico aviso seria un
    `deploy-watch` que no encuentra su dato.
    """
    payload = {"config": {"signals": {"err": {}}}, "tick_history": [{"err": 0.0}], "elapsed_secs": 0}
    data = json.loads(_cli(payload).stdout)

    assert set(data) == {"verdict", "reason", "blocking", "scorecard", "baseline_warnings"}
    assert set(data["scorecard"]["err"]) == {
        "worst",
        "breaches",
        "confirmed",
        "critical",
        "measured",
        "declarada",
    }


def test_cli_emite_el_aviso_de_baseline_ruidoso() -> None:
    """El aviso es la mitad de la salida que decide si fiarse del delta.

    Hasta ahora ningun test comprobaba que llegue a la salida del CLI, solo que la funcion lo
    calcula.
    """
    payload = {
        "config": {"signals": {"lat": {}}, "min_observe_secs": 0, "warmup_secs": 0},
        "baseline_samples": [{"lat": 1.0}, {"lat": 9.0}],
        "tick_history": [{"lat": 5.0}],
        "elapsed_secs": 120,
    }
    out = _cli(payload)
    assert out.code == 0
    avisos = json.loads(out.stdout)["baseline_warnings"]
    assert len(avisos) == 1
    assert "ruidoso" in avisos[0]
    assert "lat" in avisos[0]


def test_cli_exit_2_y_ningun_veredicto_si_la_config_es_invalida() -> None:
    """Exit 2 = error de uso, como en `controles.py`.

    Un `inconclusive` aqui haria pasar el despiste de quien invoca por un dato del deploy, que
    es lo unico peor que no responder.
    """
    out = _cli({"config": {"signals": {"err": {"declarado": True}}}})
    assert out.code == 2
    assert out.stdout == ""
    assert "declarado" in out.stderr


def test_cli_exit_2_si_una_muestra_no_es_un_numero() -> None:
    """Antes el `cast` no comprobaba nada y esto reventaba con un traceback en `float(t[sig])`.

    Lo que el CLI promete para un payload mal formado es exit 2, no un traceback.
    """
    out = _cli({"config": {"signals": {"err": {}}}, "tick_history": [{"err": "muchos"}]})
    assert out.code == 2
    assert out.stdout == ""
    assert "tick_history[0]" in out.stderr
