"""Tests de la logica pura del cuerpo del issue (issue_body.py)."""

from __future__ import annotations

import pytest

import issue_body
from issue_body import Slice, parse_body, render_slice_line, set_slice_estado

_BODY = """\
# Feature X

Intro de la feature.

## Slices
- [x] slice-01 (cantidad-vo): Crear VO [mergeada] PR #11
      AC: rechaza negativos; tests en test/domain/test_cantidad.py
- [ ] slice-02 (ajustar-stock): Caso de uso AjustarStock [esperando-merge] PR #12
      AC: emite evento StockAjustado
      AC: no toca infra directamente
- [ ] slice-03 (refactor: extraer-repo): Extraer repo [en-curso]
- [ ] slice-04 (backfill): Backfill [bloqueada: ci-roja] PR #13
- [ ] slice-05 (cleanup): Retirar flag [pendiente]
- [ ] no es una slice, ignorar
"""


def test_parse_body_ids_en_orden() -> None:
    slices = parse_body(_BODY)
    assert [s.slice_id for s in slices] == [
        "slice-01",
        "slice-02",
        "slice-03",
        "slice-04",
        "slice-05",
    ]


def test_parse_body_checkbox_x_es_mergeada() -> None:
    s01 = parse_body(_BODY)[0]
    assert s01.estado == "mergeada"
    assert s01.pr == 11
    assert s01.name == "cantidad-vo"
    assert s01.type == "feat"


def test_parse_body_estados_intermedios() -> None:
    by_id = {s.slice_id: s for s in parse_body(_BODY)}
    assert by_id["slice-02"].estado == "esperando-merge"
    assert by_id["slice-02"].pr == 12
    assert by_id["slice-03"].estado == "en-curso"
    assert by_id["slice-03"].type == "refactor"
    assert by_id["slice-03"].name == "extraer-repo"
    assert by_id["slice-04"].estado == "bloqueada"
    assert by_id["slice-04"].motivo == "ci-roja"
    assert by_id["slice-05"].estado == "pendiente"


def test_parse_body_recoge_ac() -> None:
    by_id = {s.slice_id: s for s in parse_body(_BODY)}
    assert by_id["slice-01"].ac == ["rechaza negativos; tests en test/domain/test_cantidad.py"]
    assert by_id["slice-02"].ac == ["emite evento StockAjustado", "no toca infra directamente"]
    assert by_id["slice-03"].ac == []


def test_parse_body_ignora_lineas_no_slice() -> None:
    # "- [ ] no es una slice" no debe aparecer como slice.
    assert all(s.slice_id.startswith("slice-") for s in parse_body(_BODY))


def test_set_estado_marca_mergeada_como_checkbox() -> None:
    nuevo = set_slice_estado(_BODY, "slice-02", "mergeada")
    by_id = {s.slice_id: s for s in parse_body(nuevo)}
    assert by_id["slice-02"].estado == "mergeada"
    assert "- [x] slice-02 (ajustar-stock): Caso de uso AjustarStock [mergeada] PR #12" in nuevo
    # conserva el PR aunque no se pase
    assert by_id["slice-02"].pr == 12


def test_set_estado_preserva_el_resto_del_cuerpo() -> None:
    nuevo = set_slice_estado(_BODY, "slice-03", "esperando-merge", pr=99)
    # otras slices intactas
    assert "- [x] slice-01 (cantidad-vo): Crear VO [mergeada] PR #11" in nuevo
    # AC de slice-02 intactos
    assert "      AC: no toca infra directamente" in nuevo
    # intro intacta
    assert "Intro de la feature." in nuevo
    by_id = {s.slice_id: s for s in parse_body(nuevo)}
    assert by_id["slice-03"].estado == "esperando-merge"
    assert by_id["slice-03"].pr == 99


def test_set_estado_con_motivo() -> None:
    nuevo = set_slice_estado(_BODY, "slice-05", "bloqueada", motivo="verify")
    by_id = {s.slice_id: s for s in parse_body(nuevo)}
    assert by_id["slice-05"].estado == "bloqueada"
    assert by_id["slice-05"].motivo == "verify"


def test_set_estado_preserva_trailing_newline() -> None:
    assert set_slice_estado(_BODY, "slice-05", "en-curso").endswith("\n")
    sin_nl = _BODY.rstrip("\n")
    assert not set_slice_estado(sin_nl, "slice-05", "en-curso").endswith("\n")


def test_set_estado_slice_inexistente() -> None:
    with pytest.raises(KeyError):
        set_slice_estado(_BODY, "slice-99", "en-curso")


def test_set_estado_estado_invalido() -> None:
    with pytest.raises(ValueError):
        set_slice_estado(_BODY, "slice-01", "inventado")


def test_roundtrip_render_parse() -> None:
    sl = Slice(
        slice_id="slice-07",
        name="mi-slice",
        type="fix",
        title="Arreglar cosa",
        estado="esperando-merge",
        pr=42,
    )
    line = render_slice_line(sl)
    parsed = parse_body(f"## Slices\n{line}\n")[0]
    assert parsed.slice_id == "slice-07"
    assert parsed.name == "mi-slice"
    assert parsed.type == "fix"
    assert parsed.title == "Arreglar cosa"
    assert parsed.estado == "esperando-merge"
    assert parsed.pr == 42


def test_estados_expuestos() -> None:
    assert "esperando-merge" in issue_body.ESTADOS
    assert "mergeada" in issue_body.ESTADOS
