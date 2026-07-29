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
        "duracion_s": 100,
        "coste_tokens": None,
    }
    base.update(kw)
    return base


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


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_report_cuenta_el_veredicto_viejo_como_bloqueada_controles(tmp_path: Path) -> None:
    log = tmp_path / "m.jsonl"
    _write(
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
    _write(
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
    _write(
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
