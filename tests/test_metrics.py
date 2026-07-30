"""Tests de las metricas durables (metrics.py)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

import metrics


def _row(**kw: Any) -> dict[str, Any]:
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


def test_aggregate_primer_intento_excluye_abort() -> None:
    rows = [
        _row(),  # limpio a la primera
        _row(veredicto="abortada-presupuesto", ci="none"),  # abort no es exito
    ]
    agg = metrics._aggregate(rows)
    assert agg["slices"] == 2
    assert agg["primer_intento_pct"] == 50.0


def test_aggregate_cuenta_falla_y_ci_roja() -> None:
    rows = [
        _row(veredicto="FALLA", ci="none"),
        _row(ci="red", reintentos_ci=1),
    ]
    agg = metrics._aggregate(rows)
    assert agg["verificador_falla_pct"] == 50.0
    assert agg["ci_roja_pct"] == 50.0
    assert agg["primer_intento_pct"] == 0.0


def test_bloqueada_controles_no_cuenta_como_falla_del_verificador() -> None:
    # La distincion es el proposito del veredicto nuevo: un fallo mecanico de lint/tipos
    # no es un veto del juez, y confundirlos deja inservible la calibracion del juez.
    rows = [_row(veredicto="bloqueada-controles", ci="none", reintentos_controles=2), _row()]
    agg = metrics._aggregate(rows)
    assert agg["verificador_falla_pct"] == 0.0
    assert agg["bloqueada_controles_pct"] == 50.0
    assert agg["primer_intento_pct"] == 50.0


def test_primer_intento_excluye_reintentos_de_controles() -> None:
    # Verde a la primera del juez y de la CI, pero con una vuelta por lint sucio:
    # no es "limpia a la primera".
    agg = metrics._aggregate([_row(reintentos_controles=1)])
    assert agg["primer_intento_pct"] == 0.0


def test_aggregate_media_de_reintentos_de_controles() -> None:
    agg = metrics._aggregate([_row(reintentos_controles=1), _row(reintentos_controles=3)])
    assert agg["reintentos_controles_media"] == 2.0


def test_aggregate_vacio() -> None:
    agg = metrics._aggregate([])
    assert agg["slices"] == 0
    assert agg["primer_intento_pct"] == 0.0
    assert agg["coste_tokens_media"] is None


def test_load_salta_lineas_corruptas(tmp_path: Path) -> None:
    # Regresion #5: una linea corrupta no debe reventar el report.
    p = tmp_path / "m.jsonl"
    p.write_text(
        json.dumps(_row(slice_id="s1"))
        + "\n{ esto no es json\n"
        + json.dumps(_row(slice_id="s2"))
        + "\n",
        encoding="utf-8",
    )
    rows = metrics._load(p, None)
    assert [r["slice_id"] for r in rows] == ["s1", "s2"]


def test_load_filtra_por_repo(tmp_path: Path) -> None:
    p = tmp_path / "m.jsonl"
    p.write_text(
        json.dumps(_row(repo="a", slice_id="s1"))
        + "\n"
        + json.dumps(_row(repo="b", slice_id="s2"))
        + "\n",
        encoding="utf-8",
    )
    assert [r["slice_id"] for r in metrics._load(p, "a")] == ["s1"]


def test_record_report_roundtrip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "m.jsonl"
    rec_ns = argparse.Namespace(
        repo="r",
        slice="slice-01",
        name="x",
        veredicto="PASA",
        ci="green",
        hallazgos_alta=0,
        hallazgos_media=1,
        hallazgos_baja=2,
        reintentos_implement=0,
        reintentos_controles=0,
        reintentos_ci=0,
        reintentos_verify=0,
        descartes_verify=0,
        duracion_s=10,
        coste_tokens=None,
        ts="2026-01-01T00:00:00Z",
        path=str(path),
    )
    assert metrics.record(rec_ns) == 0

    rep_ns = argparse.Namespace(repo="r", json=True, path=str(path))
    assert metrics.report(rep_ns) == 0
    last = capsys.readouterr().out.strip().splitlines()[-1]
    data = json.loads(last)
    assert data["slices"] == 1
    assert data["primer_intento_pct"] == 100.0


def test_el_agregado_llega_al_json_de_la_cli_de_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # El resto de los tests de agregacion entran por `_aggregate`/`_load`, que son privadas:
    # son puras y probarlas asi es lo que las mantiene legibles. El precio es que ninguna
    # comprueba el cableado, y `report` es lo que de verdad invoca `SKILL.md`. Esto lo ancla:
    # si el argv documentado deja de llevar los numeros a stdout, cae aqui y no en produccion.
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
    assert data["slices"] == 1  # `--repo` filtro la fila del otro repo
    assert data["verificador_falla_pct"] == 0.0


def test_cli_acepta_bloqueada_controles_y_reintentos_de_controles(tmp_path: Path) -> None:
    # El camino de cierre nuevo tiene que poder registrarse desde la CLI que documenta
    # SKILL.md; si no, el log miente sobre por que paro la slice.
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


# --- compatibilidad de los registros escritos como "puertas" ---------------
#
# El log es durable y vive fuera del repo: los registros historicos llevan el veredicto
# `bloqueada-puertas` y el campo `reintentos_puertas`. Renombrar no puede borrar historico.


def test_report_cuenta_el_veredicto_viejo_como_bloqueada_controles(tmp_path: Path) -> None:
    log = tmp_path / "m.jsonl"
    _escribe_log(
        log,
        [
            {"repo": "r", "veredicto": "bloqueada-puertas", "ci": "none"},
            {"repo": "r", "veredicto": "bloqueada-controles", "ci": "none"},
        ],
    )
    agg = metrics._aggregate(metrics._load(log, "r"))
    assert agg["bloqueada_controles_pct"] == 100.0


def test_report_promedia_los_reintentos_con_el_campo_viejo(tmp_path: Path) -> None:
    log = tmp_path / "m.jsonl"
    _escribe_log(
        log,
        [
            {"repo": "r", "veredicto": "PASA", "ci": "green", "reintentos_puertas": 2},
            {"repo": "r", "veredicto": "PASA", "ci": "green", "reintentos_controles": 0},
        ],
    )
    agg = metrics._aggregate(metrics._load(log, "r"))
    assert agg["reintentos_controles_media"] == 1.0


def test_una_fila_vieja_con_reintentos_no_cuenta_como_primer_intento(tmp_path: Path) -> None:
    # Sin leer el campo viejo, esta fila pasaria por "limpia a la primera" y falsearia
    # justo la cifra que sirve para decidir si subir de nivel.
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
    agg = metrics._aggregate(metrics._load(log, "r"))
    assert agg["primer_intento_pct"] == 0.0


# --- reintentos y descartes del verificador ---------------------------------
#
# Se registran en dos campos distintos por el mismo motivo por el que `FALLA` y
# `bloqueada-controles` son veredictos distintos: un `FALLA` es un rechazo semantico del
# juez y devolver prosa en vez de su JSON es un fallo mecanico del agente. Conflarlos
# dejaria inservible justo lo que se quiere medir. El segundo caso aparecio en el smoke 2
# (2026-07-30): la misma invocacion devolvio prosa una vez y JSON pelado al reintentarla,
# asi que es estocastico y hay que poder medirlo.


def test_descartes_del_verificador_no_cuentan_como_reintento_semantico() -> None:
    # Una slice cuyo unico incidente fue que el juez devolvio prosa: su media de reintentos
    # semanticos es 0, pero la tasa de contrato roto es 100%. Si se sumaran en el mismo
    # campo, un fallo del agente se leeria como que el juez veto codigo.
    agg = metrics._aggregate([_row(reintentos_verify=0, descartes_verify=1)])
    assert agg["reintentos_verify_media"] == 0.0
    assert agg["descartes_verify_pct"] == 100.0


def test_un_descarte_no_descalifica_el_primer_intento() -> None:
    # El juez reescribio su respuesta, no la slice: el codigo salio limpio a la primera.
    # Contarlo contra "primer intento" mediria la disciplina del agente como si fuera
    # calidad del codigo.
    agg = metrics._aggregate([_row(descartes_verify=1)])
    assert agg["primer_intento_pct"] == 100.0


def test_media_de_reintentos_semanticos_del_verificador() -> None:
    agg = metrics._aggregate([_row(reintentos_verify=2), _row(reintentos_verify=0)])
    assert agg["reintentos_verify_media"] == 1.0


def test_filas_viejas_sin_los_campos_nuevos_se_agregan_igual() -> None:
    # El log es durable y hay filas escritas antes de que estos campos existieran: leerlas
    # no puede petar ni inventarse un valor. Mismo trato que `reintentos_puertas`.
    vieja = _row()
    del vieja["reintentos_verify"]
    del vieja["descartes_verify"]
    agg = metrics._aggregate([vieja])
    assert agg["reintentos_verify_media"] == 0.0
    assert agg["descartes_verify_pct"] == 0.0


def test_cli_acepta_y_persiste_los_dos_campos(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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
