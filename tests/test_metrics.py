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
        "reintentos_puertas": 0,
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


def test_bloqueada_puertas_no_cuenta_como_falla_del_verificador() -> None:
    # La distincion es el proposito del veredicto nuevo: un fallo mecanico de lint/tipos
    # no es un veto del juez, y confundirlos deja inservible la calibracion del juez.
    rows = [_row(veredicto="bloqueada-puertas", ci="none", reintentos_puertas=2), _row()]
    agg = metrics._aggregate(rows)
    assert agg["verificador_falla_pct"] == 0.0
    assert agg["bloqueada_puertas_pct"] == 50.0
    assert agg["primer_intento_pct"] == 50.0


def test_primer_intento_excluye_reintentos_de_puertas() -> None:
    # Verde a la primera del juez y de la CI, pero con una vuelta por lint sucio:
    # no es "limpia a la primera".
    agg = metrics._aggregate([_row(reintentos_puertas=1)])
    assert agg["primer_intento_pct"] == 0.0


def test_aggregate_media_de_reintentos_de_puertas() -> None:
    agg = metrics._aggregate([_row(reintentos_puertas=1), _row(reintentos_puertas=3)])
    assert agg["reintentos_puertas_media"] == 2.0


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
        reintentos_puertas=0,
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


def test_cli_acepta_bloqueada_puertas_y_reintentos_de_puertas(tmp_path: Path) -> None:
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
            "bloqueada-puertas",
            "--ci",
            "none",
            "--reintentos-puertas",
            "2",
            "--path",
            str(path),
        ]
    )
    assert code == 0
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["veredicto"] == "bloqueada-puertas"
    assert row["reintentos_puertas"] == 2
