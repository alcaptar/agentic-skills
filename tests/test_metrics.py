"""Tests de las metricas durables (metrics.py)."""

from __future__ import annotations

import argparse
import json
from typing import TYPE_CHECKING, Any

import pytest

import metrics
from metrics import CausaDescarte, Ci, Fila, Hallazgos, Registro, Veredicto

if TYPE_CHECKING:
    from pathlib import Path


def _fila(**kw: Any) -> Fila:
    """Una fila del log ya normalizada, con defaults de "slice limpia a la primera".

    Los tests de agregacion hablan de filas, no de JSON: entran por `Fila` y dejan
    `Fila.from_row` -la capa de compatibilidad historica- a los tests que van de eso.
    """
    base: dict[str, Any] = {
        "repo": "r",
        "slice_id": "slice-01",
        "veredicto": Veredicto.PASA,
        "ci": Ci.VERDE,
        "reintentos_implement": 0.0,
        "reintentos_controles": 0.0,
        "reintentos_ci": 0.0,
        "reintentos_verify": 0.0,
        "descartes_verify": 0.0,
        "duracion_s": 100.0,
        "coste_tokens": None,
        "coste_usd": None,
        "turnos": None,
        "duracion_ms": None,
        "tokens_cache": None,
        "descartes_verify_causa": None,
        "modelos": (),
        "variante": None,
    }
    return Fila(**{**base, **kw})


def _row(**kw: Any) -> dict[str, Any]:
    """Una fila tal cual se escribe en el log (JSON), para los tests que entran por ahi."""
    base: dict[str, Any] = {
        "repo": "r",
        "slice_id": "slice-01",
        "name": "x",
        "veredicto": "PASA",
        "ci": "green",
        "reintentos_implement": 0,
        "reintentos_controles": 0,
        "reintentos_ci": 0,
        "reintentos_verify": 0,
        "descartes_verify": 0,
        "duracion_s": 100,
        "coste_tokens": None,
    }
    base.update(kw)
    return base


def _escribe_log(path: Path, rows: list[dict[str, object]]) -> None:
    """Un log JSON por lineas ya escrito, para partir de historico en vez de de `record`."""
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _record(path: Path, *extra: str) -> list[str]:
    """El argv minimo de `record` sobre un log de usar y tirar, mas lo que anada cada test."""
    return [
        "record",
        "--repo",
        "r",
        "--slice",
        "slice-01",
        "--name",
        "x",
        "--veredicto",
        "PASA",
        "--ci",
        "green",
        "--path",
        str(path),
        *extra,
    ]


def _escrita(path: Path) -> dict[str, Any]:
    """La unica fila que `record` acaba de anexar, tal cual quedo en el log."""
    fila: dict[str, Any] = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    return fila


def test_aggregate_primer_intento_excluye_abort() -> None:
    """Una fila limpia cuenta como primer intento; un abort por presupuesto no es exito."""
    filas = [_fila(), _fila(veredicto=Veredicto.ABORTADA_PRESUPUESTO, ci=Ci.NINGUNA)]
    agg = metrics._aggregate(filas)
    assert agg.slices == 2
    assert agg.primer_intento_pct == 50.0


def test_aggregate_cuenta_falla_y_ci_roja() -> None:
    filas = [
        _fila(veredicto=Veredicto.FALLA, ci=Ci.NINGUNA),
        _fila(ci=Ci.ROJA, reintentos_ci=1.0),
    ]
    agg = metrics._aggregate(filas)
    assert agg.verificador_falla_pct == 50.0
    assert agg.ci_roja_pct == 50.0
    assert agg.primer_intento_pct == 0.0


def test_bloqueada_controles_no_cuenta_como_falla_del_verificador() -> None:
    """La distincion es el proposito del veredicto nuevo.

    Un fallo mecanico de lint/tipos no es un veto del juez, y confundirlos deja inservible la
    calibracion del juez.
    """
    filas = [
        _fila(veredicto=Veredicto.BLOQUEADA_CONTROLES, ci=Ci.NINGUNA, reintentos_controles=2.0),
        _fila(),
    ]
    agg = metrics._aggregate(filas)
    assert agg.verificador_falla_pct == 0.0
    assert agg.bloqueada_controles_pct == 50.0
    assert agg.primer_intento_pct == 50.0


def test_primer_intento_excluye_reintentos_de_controles() -> None:
    """Verde a la primera del juez y de la CI, pero con una vuelta por lint sucio: no es limpia."""
    agg = metrics._aggregate([_fila(reintentos_controles=1.0)])
    assert agg.primer_intento_pct == 0.0


def test_aggregate_media_de_reintentos_de_controles() -> None:
    agg = metrics._aggregate([_fila(reintentos_controles=1.0), _fila(reintentos_controles=3.0)])
    assert agg.reintentos_controles_media == 2.0


def test_aggregate_vacio() -> None:
    agg = metrics._aggregate([])
    assert agg.slices == 0
    assert agg.primer_intento_pct == 0.0
    assert agg.coste_tokens_media is None


def test_load_salta_lineas_corruptas(tmp_path: Path) -> None:
    """Regresion #5: una linea corrupta no debe reventar el report."""
    p = tmp_path / "m.jsonl"
    p.write_text(
        json.dumps(_row(slice_id="s1")) + "\n{ esto no es json\n" + json.dumps(_row(slice_id="s2")) + "\n",
        encoding="utf-8",
    )
    assert [f.slice_id for f in metrics._load(p, None)] == ["s1", "s2"]


def test_load_filtra_por_repo(tmp_path: Path) -> None:
    p = tmp_path / "m.jsonl"
    p.write_text(
        json.dumps(_row(repo="a", slice_id="s1")) + "\n" + json.dumps(_row(repo="b", slice_id="s2")) + "\n",
        encoding="utf-8",
    )
    assert [f.slice_id for f in metrics._load(p, "a")] == ["s1"]


def test_record_report_roundtrip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "m.jsonl"
    registro = Registro(
        ts="2026-01-01T00:00:00Z",
        repo="r",
        slice_id="slice-01",
        name="x",
        veredicto=Veredicto.PASA,
        ci=Ci.VERDE,
        hallazgos=Hallazgos(media=1, baja=2),
        duracion_s=10,
    )

    metrics.escribe(registro, path)

    assert metrics.report(argparse.Namespace(repo="r", json=True, path=str(path))) == 0
    data = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert data["slices"] == 1
    assert data["primer_intento_pct"] == 100.0


def test_las_claves_del_registro_son_el_formato_del_log_durable() -> None:
    """El log sobrevive a los runs y hay historico escrito con estas claves.

    Renombrar un campo del dataclass no puede cambiarlas, o el agregado deja de encontrar las
    filas viejas. Los enums se serializan como su cadena, no como `Veredicto.PASA`.
    """
    registro = Registro(
        ts="2026-01-01T00:00:00Z",
        repo="r",
        slice_id="slice-01",
        name="x",
        veredicto=Veredicto.PASA,
        ci=Ci.VERDE,
        hallazgos=Hallazgos(),
    )

    escrito = registro.to_dict()

    assert set(escrito) == {
        "ts",
        "repo",
        "slice_id",
        "name",
        "veredicto",
        "ci",
        "hallazgos",
        "hallazgos_ronda_final",
        "reintentos_implement",
        "reintentos_controles",
        "reintentos_ci",
        "reintentos_verify",
        "descartes_verify",
        "duracion_s",
        "coste_tokens",
    }
    assert escrito["hallazgos"] == {"alta": 0, "media": 0, "baja": 0}
    assert escrito["hallazgos_ronda_final"] == {"alta": 0, "media": 0, "baja": 0}
    assert escrito["veredicto"] == "PASA"
    assert escrito["ci"] == "green"


def test_el_agregado_llega_al_json_de_la_cli_de_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """El resto de los tests de agregacion entran por `_aggregate`/`_load`, que son privadas.

    Son puras y probarlas asi es lo que las mantiene legibles. El precio es que ninguna comprueba
    el cableado, y `report` es lo que de verdad invoca `SKILL.md`. Esto lo ancla: si el argv
    documentado deja de llevar los numeros a stdout, cae aqui y no en produccion.
    """
    log = tmp_path / "m.jsonl"
    _escribe_log(
        log,
        [
            {"repo": "r", "veredicto": "PASA", "ci": "green"},
            {"repo": "otro", "veredicto": "FALLA", "ci": "none"},
        ],
    )

    assert metrics.main(["report", "--repo", "r", "--path", str(log), "--json"]) == 0

    data = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert data["slices"] == 1
    assert data["verificador_falla_pct"] == 0.0


def test_cli_acepta_bloqueada_controles_y_reintentos_de_controles(tmp_path: Path) -> None:
    """El camino de cierre nuevo tiene que poder registrarse desde la CLI que documenta SKILL.md.

    Si no, el log miente sobre por que paro la slice.
    """
    path = tmp_path / "m.jsonl"
    code = metrics.main(
        [
            "record",
            "--repo",
            "r",
            "--slice",
            "slice-01",
            "--name",
            "x",
            "--veredicto",
            "bloqueada-controles",
            "--ci",
            "none",
            "--reintentos-controles",
            "2",
            "--path",
            str(path),
        ]
    )
    assert code == 0
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["veredicto"] == "bloqueada-controles"
    assert row["reintentos_controles"] == 2


def test_report_cuenta_el_veredicto_viejo_como_bloqueada_controles(tmp_path: Path) -> None:
    """El log es durable y vive fuera del repo: hay filas con el veredicto `bloqueada-puertas`.

    Renombrar no puede borrar historico.
    """
    log = tmp_path / "m.jsonl"
    _escribe_log(
        log,
        [
            {"repo": "r", "veredicto": "bloqueada-puertas", "ci": "none"},
            {"repo": "r", "veredicto": "bloqueada-controles", "ci": "none"},
        ],
    )
    assert metrics._aggregate(metrics._load(log, "r")).bloqueada_controles_pct == 100.0


def test_report_promedia_los_reintentos_con_el_campo_viejo(tmp_path: Path) -> None:
    """Mismo trato para el campo `reintentos_puertas` que para el veredicto viejo."""
    log = tmp_path / "m.jsonl"
    _escribe_log(
        log,
        [
            {"repo": "r", "veredicto": "PASA", "ci": "green", "reintentos_puertas": 2},
            {"repo": "r", "veredicto": "PASA", "ci": "green", "reintentos_controles": 0},
        ],
    )
    assert metrics._aggregate(metrics._load(log, "r")).reintentos_controles_media == 1.0


def test_una_fila_vieja_con_reintentos_no_cuenta_como_primer_intento(tmp_path: Path) -> None:
    """Sin leer el campo viejo, esta fila pasaria por "limpia a la primera".

    Falsearia justo la cifra que sirve para decidir si subir de nivel.
    """
    log = tmp_path / "m.jsonl"
    _escribe_log(
        log,
        [
            {
                "repo": "r",
                "veredicto": "PASA",
                "ci": "green",
                "reintentos_implement": 0,
                "reintentos_puertas": 1,
                "reintentos_ci": 0,
            }
        ],
    )
    assert metrics._aggregate(metrics._load(log, "r")).primer_intento_pct == 0.0


def test_descartes_del_verificador_no_cuentan_como_reintento_semantico() -> None:
    """Los dos campos estan separados por el mismo motivo que `FALLA` y `bloqueada-controles`.

    Un `FALLA` es un rechazo semantico del juez y devolver prosa en vez de su JSON es un fallo
    mecanico del agente; conflarlos dejaria inservible justo lo que se quiere medir. El segundo
    caso aparecio en el smoke 2 (2026-07-30): la misma invocacion devolvio prosa una vez y JSON
    pelado al reintentarla, asi que es estocastico y hay que poder medirlo.

    Esta slice tuvo un unico incidente -el juez devolvio prosa-: su media de reintentos
    semanticos es 0, pero la tasa de contrato roto es 100%.
    """
    agg = metrics._aggregate([_fila(reintentos_verify=0.0, descartes_verify=1.0)])
    assert agg.reintentos_verify_media == 0.0
    assert agg.descartes_verify_pct == 100.0


def test_un_descarte_no_descalifica_el_primer_intento() -> None:
    """El juez reescribio su respuesta, no la slice: el codigo salio limpio a la primera.

    Contarlo contra "primer intento" mediria la disciplina del agente como si fuera calidad del
    codigo.
    """
    assert metrics._aggregate([_fila(descartes_verify=1.0)]).primer_intento_pct == 100.0


def test_media_de_reintentos_semanticos_del_verificador() -> None:
    agg = metrics._aggregate([_fila(reintentos_verify=2.0), _fila(reintentos_verify=0.0)])
    assert agg.reintentos_verify_media == 1.0


def test_filas_viejas_sin_los_campos_nuevos_se_agregan_igual() -> None:
    """Hay filas escritas antes de que estos campos existieran: leerlas no puede petar.

    Tampoco puede inventarse un valor. Mismo trato que `reintentos_puertas`.
    """
    vieja = _row()
    del vieja["reintentos_verify"]
    del vieja["descartes_verify"]
    agg = metrics._aggregate([Fila.from_row(vieja)])
    assert agg.reintentos_verify_media == 0.0
    assert agg.descartes_verify_pct == 0.0


def test_cli_acepta_y_persiste_los_dos_campos(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "m.jsonl"
    code = metrics.main(
        [
            "record",
            "--repo",
            "r",
            "--slice",
            "slice-01",
            "--name",
            "x",
            "--veredicto",
            "PASA",
            "--ci",
            "green",
            "--reintentos-verify",
            "1",
            "--descartes-verify",
            "1",
            "--path",
            str(path),
        ]
    )
    assert code == 0
    capsys.readouterr()
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["reintentos_verify"] == 1
    assert row["descartes_verify"] == 1

    metrics.main(["report", "--path", str(path)])
    out = capsys.readouterr().out
    assert "reintentos verify" in out
    assert "contrato del juez roto" in out


def test_el_gasto_del_harness_se_escribe_como_un_grupo_anidado(tmp_path: Path) -> None:
    """Los cuatro numeros salen de la misma suma del JSON del harness, asi que viajan juntos.

    Sueltos, la fila no diria de cuantas llamadas es cada uno; agrupados, `harness` significa
    "esto es lo que midio el harness" y se distingue de los campos que estima quien invoca.
    """
    path = tmp_path / "m.jsonl"

    assert (
        metrics.main(
            _record(path, "--coste-usd", "0.42", "--turnos", "14", "--duracion-ms", "65652", "--tokens-cache", "15510")
        )
        == 0
    )

    assert _escrita(path)["harness"] == {
        "coste_usd": 0.42,
        "turnos": 14,
        "duracion_ms": 65652,
        "tokens_cache": 15510,
    }


def test_los_hallazgos_de_la_ronda_final_viajan_aparte_de_los_acumulados(tmp_path: Path) -> None:
    """Una fila `PASA` con un `alta` acumulado deja de leerse como `veredicto-incoherente`.

    `--hallazgos-alta` acumula los de todas las rondas del verificador, y `Verdict` impide que la
    ronda final de un `PASA` traiga un `alta` -por eso las dos filas dejan de confundirse: la que de
    verdad se contradice no puede llegar aqui-.
    """
    path = tmp_path / "m.jsonl"

    assert metrics.main(_record(path, "--hallazgos-alta", "1", "--hallazgos-ronda-final-alta", "0")) == 0

    escrita = _escrita(path)
    assert escrita["hallazgos"]["alta"] == 1
    assert escrita["hallazgos_ronda_final"]["alta"] == 0


def test_sin_pasar_la_ronda_final_se_registra_como_cero_y_no_como_ausente(tmp_path: Path) -> None:
    path = tmp_path / "m.jsonl"

    assert metrics.main(_record(path)) == 0

    assert _escrita(path)["hallazgos_ronda_final"] == {"alta": 0, "media": 0, "baja": 0}


def test_sin_datos_del_harness_no_se_escribe_la_clave(tmp_path: Path) -> None:
    """Ningun numero se estima: un cero o un `null` no se distinguen de "no lo he medido"."""
    path = tmp_path / "m.jsonl"

    assert metrics.main(_record(path)) == 0

    assert "harness" not in _escrita(path)


def test_pasar_un_dato_del_harness_y_no_los_otros_dos_es_error_de_uso(tmp_path: Path) -> None:
    """Media suma es un dato que nadie puede interpretar, y no se puede completar inventandolo."""
    path = tmp_path / "m.jsonl"

    with pytest.raises(SystemExit) as salida:
        metrics.main(_record(path, "--coste-usd", "0.42"))

    assert salida.value.code == 2
    assert not path.exists()


def test_la_causa_del_descarte_viaja_junto_a_su_contador(tmp_path: Path) -> None:
    """El contador dice cuantas veces, la causa dice de que clase de fallo se esta hablando.

    Un juez que contesta su JSON con un veredicto que se contradice y una llamada que ni llego a
    devolver el sobre son cosas distintas, y sin la causa el agregado no puede separarlas.
    """
    path = tmp_path / "m.jsonl"

    assert metrics.main(_record(path, "--descartes-verify", "2", "--descartes-verify-causa", "llamada-fallida")) == 0

    fila = _escrita(path)
    assert (fila["descartes_verify"], fila["descartes_verify_causa"]) == (2, "llamada-fallida")


def test_una_causa_sin_descartes_es_error_de_uso(tmp_path: Path) -> None:
    """No hay descarte al que atribuirla, asi que la fila mentiria sobre lo que paso."""
    path = tmp_path / "m.jsonl"

    with pytest.raises(SystemExit) as salida:
        metrics.main(_record(path, "--descartes-verify-causa", "veredicto-incoherente"))

    assert salida.value.code == 2
    assert not path.exists()


def test_los_descartes_sin_causa_se_siguen_aceptando(tmp_path: Path) -> None:
    """El flujo viejo no sabe la causa y el historico no la trae: exigirla romperia el registro."""
    path = tmp_path / "m.jsonl"

    assert metrics.main(_record(path, "--descartes-verify", "1")) == 0

    fila = _escrita(path)
    assert fila["descartes_verify"] == 1
    assert "descartes_verify_causa" not in fila


def test_una_causa_que_no_esta_en_el_vocabulario_no_se_registra(tmp_path: Path) -> None:
    """El vocabulario es cerrado: una tercera causa inventada haria incomparable el reparto."""
    path = tmp_path / "m.jsonl"

    with pytest.raises(SystemExit) as salida:
        metrics.main(_record(path, "--descartes-verify", "1", "--descartes-verify-causa", "se-aburrio"))

    assert salida.value.code == 2
    assert not path.exists()


def test_el_report_promedia_el_coste_en_dolares_de_las_filas_que_lo_traen() -> None:
    """Mismo trato que el coste en tokens: media y numero de muestras, nunca cero por defecto.

    Promediar contando las filas sin dato como cero hundiria la media justo cuando se empieza a
    medir, que es cuando la cifra se usa para decidir si subir de nivel.
    """
    filas = [_fila(coste_usd=0.20), _fila(coste_usd=0.40), _fila()]

    agg = metrics._aggregate(filas)

    assert (agg.coste_usd_media, agg.coste_usd_muestras) == (0.3, 2)


def test_el_report_promedia_los_turnos_y_la_duracion_igual_que_el_coste() -> None:
    """Los tres numeros del grupo se agregan, no solo el coste: si no, dos se escriben para nadie.

    Mismo trato exacto: media de las filas que lo traen y cuantas eran, sin contar como cero las
    que no lo traen.
    """
    filas = [_fila(turnos=9.0, duracion_ms=36315.0), _fila(turnos=5.0, duracion_ms=29337.0), _fila()]

    agg = metrics._aggregate(filas)

    assert (agg.turnos_media, agg.turnos_muestras) == (7.0, 2)
    assert (agg.duracion_ms_media, agg.duracion_ms_muestras) == (32826.0, 2)


def test_sin_ninguna_fila_del_harness_las_tres_medidas_son_sin_datos() -> None:
    """`None` y `0.0` no son lo mismo: uno dice "no medido" y el otro "salio gratis en cero turnos"."""
    agg = metrics._aggregate([_fila()])

    assert (agg.coste_usd_media, agg.turnos_media, agg.duracion_ms_media) == (None, None, None)
    assert (agg.coste_usd_muestras, agg.turnos_muestras, agg.duracion_ms_muestras) == (0, 0, 0)


def test_una_fila_sin_el_grupo_del_harness_se_agrega_sin_error() -> None:
    """Hay historico escrito antes de que el grupo existiera: leerlo no puede petar ni inventar."""
    vieja = _row()

    fila = Fila.from_row(vieja)

    assert (fila.coste_usd, fila.turnos, fila.duracion_ms) == (None, None, None)
    assert fila.descartes_verify_causa is None


def test_los_tres_numeros_del_harness_salen_del_grupo_anidado() -> None:
    """La compatibilidad historica vive en un solo sitio, y el grupo se lee ahi como los demas.

    Los tres, no solo el coste: escribir un numero que el agregado no lee es escribirlo para nadie.
    """
    fila = Fila.from_row(_row(harness={"coste_usd": 0.42, "turnos": 14, "duracion_ms": 65652}))

    assert (fila.coste_usd, fila.turnos, fila.duracion_ms) == (0.42, 14.0, 65652.0)


def test_un_grupo_del_harness_a_medias_no_completa_los_que_falten_con_ceros() -> None:
    """El escritor no puede emitirlo asi, pero el lector es tolerante y no puede inventar.

    Cero turnos medidos y turnos no medidos no son lo mismo, y confundirlos hundiria la media.
    """
    fila = Fila.from_row(_row(harness={"coste_usd": 0.42}))

    assert (fila.coste_usd, fila.turnos, fila.duracion_ms) == (0.42, None, None)


def test_el_reparto_de_descartes_por_causa_solo_cuenta_las_filas_que_la_declaran() -> None:
    """Un campo que se escribe y nadie agrega no sirve para decidir; repartir a ojo, tampoco.

    Las filas con descartes pero sin causa -el flujo viejo y el historico- no entran en ninguna de
    las dos, en vez de imputarse a la mas comun.
    """
    filas = [
        _fila(descartes_verify=1.0, descartes_verify_causa=CausaDescarte.LLAMADA_FALLIDA),
        _fila(descartes_verify=1.0, descartes_verify_causa=CausaDescarte.VEREDICTO_INCOHERENTE),
        _fila(descartes_verify=3.0, descartes_verify_causa=CausaDescarte.VEREDICTO_INCOHERENTE),
        _fila(descartes_verify=1.0),
    ]

    agg = metrics._aggregate(filas)

    assert agg.to_dict()["descartes_por_causa"] == {"veredicto-incoherente": 2, "llamada-fallida": 1}
    assert agg.descartes_verify_pct == 100.0


def test_una_causa_que_el_log_no_reconoce_se_lee_como_ausente_en_vez_de_reventar() -> None:
    """El log es durable: una fila rara no puede tumbar el agregado de todo el historico legible.

    Mismo criterio que saltarse una linea corrupta en `_load`.
    """
    fila = Fila.from_row(_row(descartes_verify=1, descartes_verify_causa="se-aburrio"))

    assert fila.descartes_verify_causa is None


def test_el_coste_en_dolares_y_el_reparto_de_causas_llegan_al_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """El cableado de `report`, que es lo que de verdad lanza una persona.

    Si los numeros nuevos se quedan en `_aggregate` y no salen por stdout, el dato existe y nadie
    puede leerlo, que para decidir es lo mismo que no tenerlo.
    """
    log = tmp_path / "m.jsonl"
    _escribe_log(
        log,
        [
            {
                "repo": "r",
                "veredicto": "PASA",
                "ci": "green",
                "descartes_verify": 1,
                "descartes_verify_causa": "llamada-fallida",
                "harness": {"coste_usd": 0.5, "turnos": 14, "duracion_ms": 65652},
            }
        ],
    )

    assert metrics.main(["report", "--repo", "r", "--path", str(log), "--json"]) == 0

    data = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert (data["coste_usd_media"], data["coste_usd_muestras"]) == (0.5, 1)
    assert (data["turnos_media"], data["turnos_muestras"]) == (14.0, 1)
    assert (data["duracion_ms_media"], data["duracion_ms_muestras"]) == (65652.0, 1)
    assert data["descartes_por_causa"] == {"veredicto-incoherente": 0, "llamada-fallida": 1}

    assert metrics.main(["report", "--repo", "r", "--path", str(log)]) == 0
    salida = capsys.readouterr().out
    assert "coste $" in salida
    assert "turnos del harness" in salida
    assert "duracion del harness" in salida


def test_las_medidas_del_harness_que_ninguna_fila_trae_se_reportan_como_sin_datos(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Una media de `0.0` donde no hay medicion se lee como un dato, y decidir con ella es peor que no tenerla."""
    log = tmp_path / "m.jsonl"
    _escribe_log(log, [{"repo": "r", "veredicto": "PASA", "ci": "green"}])

    assert metrics.main(["report", "--repo", "r", "--path", str(log)]) == 0

    for linea in capsys.readouterr().out.splitlines():
        if linea.startswith(("  coste $", "  turnos del harness", "  duracion del harness")):
            assert "sin datos" in linea


def test_el_modelo_declarado_por_el_harness_se_persiste(tmp_path: Path) -> None:
    """`--modelo` es lo que el harness dijo haber usado, nunca el alias que se le pidio."""
    path = tmp_path / "m.jsonl"

    assert metrics.main(_record(path, "--modelo", "claude-sonnet-5")) == 0

    assert _escrita(path)["modelos"] == ["claude-sonnet-5"]


def test_una_slice_que_uso_mas_de_un_modelo_los_guarda_todos_en_vez_de_quedarse_con_uno(tmp_path: Path) -> None:
    """Implementador y juez -o un reintento que cambio de modelo- pueden no coincidir.

    Quedarse con el primero silenciaria justo el caso que el criterio de aceptacion pide reflejar.
    """
    path = tmp_path / "m.jsonl"

    assert metrics.main(_record(path, "--modelo", "claude-sonnet-5", "--modelo", "claude-haiku-4-5-20251001")) == 0

    assert _escrita(path)["modelos"] == ["claude-sonnet-5", "claude-haiku-4-5-20251001"]


def test_sin_modelo_declarado_la_clave_no_se_escribe(tmp_path: Path) -> None:
    """No inventar un modelo cuando no se declaro ninguno: ausente, no una lista vacia visible."""
    path = tmp_path / "m.jsonl"

    assert metrics.main(_record(path)) == 0

    assert "modelos" not in _escrita(path)


def test_la_variante_del_pipeline_se_persiste_cuando_se_declara(tmp_path: Path) -> None:
    path = tmp_path / "m.jsonl"

    assert metrics.main(_record(path, "--variante", "programa")) == 0

    assert _escrita(path)["variante"] == "programa"


def test_sin_variante_declarada_la_clave_no_se_escribe(tmp_path: Path) -> None:
    path = tmp_path / "m.jsonl"

    assert metrics.main(_record(path)) == 0

    assert "variante" not in _escrita(path)


def test_tokens_cache_viaja_con_los_otros_tres_numeros_del_harness(tmp_path: Path) -> None:
    path = tmp_path / "m.jsonl"

    assert (
        metrics.main(
            _record(path, "--coste-usd", "0.42", "--turnos", "14", "--duracion-ms", "65652", "--tokens-cache", "15510")
        )
        == 0
    )

    assert _escrita(path)["harness"]["tokens_cache"] == 15510


def test_tokens_cache_sin_los_otros_tres_numeros_del_harness_es_error_de_uso(tmp_path: Path) -> None:
    """Media suma con `tokens_cache` incluido es exactamente el mismo fallo que sin el."""
    path = tmp_path / "m.jsonl"

    with pytest.raises(SystemExit) as salida:
        metrics.main(_record(path, "--tokens-cache", "15510"))

    assert salida.value.code == 2
    assert not path.exists()


def test_una_fila_con_varios_modelos_los_lee_todos_de_la_lista() -> None:
    fila = Fila.from_row(_row(modelos=["claude-sonnet-5", "claude-haiku-4-5-20251001"]))

    assert fila.modelos == ("claude-sonnet-5", "claude-haiku-4-5-20251001")


def test_una_fila_historica_sin_modelo_ni_variante_se_lee_como_ausente_y_no_como_vacio() -> None:
    """Historico anterior a esta slice: ni la clave `modelos` ni `variante` existen todavia."""
    fila = Fila.from_row(_row())

    assert fila.modelos == ()
    assert fila.variante is None


def test_una_fila_sin_modelo_se_agrupa_como_desconocido_y_no_se_mezcla_con_uno_real() -> None:
    filas = [_fila(modelos=("claude-sonnet-5",)), _fila(modelos=())]

    agg = metrics._aggregate(filas)

    assert set(agg.por_modelo) == {"claude-sonnet-5", metrics.DESCONOCIDO}
    assert agg.por_modelo["claude-sonnet-5"].slices == 1
    assert agg.por_modelo[metrics.DESCONOCIDO].slices == 1


def test_una_fila_con_dos_modelos_cuenta_en_los_dos_grupos_a_la_vez() -> None:
    """Reflejar los dos, no elegir uno: es el criterio de aceptacion sobre una slice con mas de un modelo."""
    filas = [_fila(modelos=("claude-sonnet-5", "claude-haiku-4-5-20251001"))]

    agg = metrics._aggregate(filas)

    assert agg.por_modelo["claude-sonnet-5"].slices == 1
    assert agg.por_modelo["claude-haiku-4-5-20251001"].slices == 1


def test_el_reparto_por_variante_separa_las_filas_por_su_variante_declarada() -> None:
    filas = [
        _fila(variante="programa", coste_usd=0.10),
        _fila(variante="programa", coste_usd=0.30),
        _fila(variante="agente", coste_usd=1.00),
        _fila(variante=None, coste_usd=2.00),
    ]

    agg = metrics._aggregate(filas)

    assert (agg.por_variante["programa"].slices, agg.por_variante["programa"].coste_usd_media) == (2, 0.2)
    assert (agg.por_variante["agente"].slices, agg.por_variante["agente"].coste_usd_media) == (1, 1.0)
    assert (agg.por_variante[metrics.DESCONOCIDO].slices, agg.por_variante[metrics.DESCONOCIDO].coste_usd_media) == (
        1,
        2.0,
    )


def test_el_reparto_por_modelo_y_variante_llega_al_json_del_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """El cableado de `report`: si el reparto se queda en `_aggregate`, nadie lo puede leer."""
    log = tmp_path / "m.jsonl"
    _escribe_log(
        log,
        [
            {
                "repo": "r",
                "veredicto": "PASA",
                "ci": "green",
                "modelos": ["claude-sonnet-5"],
                "variante": "programa",
                "harness": {"coste_usd": 0.3, "turnos": 9, "duracion_ms": 36315, "tokens_cache": 241303},
            },
            {"repo": "r", "veredicto": "PASA", "ci": "green"},
        ],
    )

    assert metrics.main(["report", "--repo", "r", "--path", str(log), "--json"]) == 0

    data = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert data["por_modelo"]["claude-sonnet-5"]["slices"] == 1
    assert data["por_modelo"][metrics.DESCONOCIDO]["slices"] == 1
    assert data["por_variante"]["programa"]["coste_usd_media"] == 0.3
    assert data["tokens_cache_media"] == 241303.0

    assert metrics.main(["report", "--repo", "r", "--path", str(log)]) == 0
    salida = capsys.readouterr().out
    assert "por modelo:" in salida
    assert "por variante:" in salida
    assert "claude-sonnet-5" in salida
    assert "programa" in salida
    assert "tokens de cache" in salida
