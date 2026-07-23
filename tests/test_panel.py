"""Tests del panel (panel/slice-panel.py), cargado via la fixture `panel`."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType


def test_parse_spec_con_name_y_type(panel: ModuleType, tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(
        "## Slices\n"
        "- [ ] slice-01 (cantidad-vo): Crear VO\n"
        "      AC: rechaza negativos\n"
        "- [x] slice-02 (refactor: extraer-repo): Extraer repo\n",
        encoding="utf-8",
    )
    slices = panel._parse_spec(spec)
    assert [s["slice_id"] for s in slices] == ["slice-01", "slice-02"]
    assert slices[0]["name"] == "cantidad-vo"
    assert slices[1]["name"] == "extraer-repo"  # el type se descarta, queda el name
    assert slices[1]["box_estado"] == "hecha"


def test_parse_spec_ignora_lineas_no_slice(panel: ModuleType, tmp_path: Path) -> None:
    # Regresion #4: un checkbox que no sea `slice-NN` no se cuenta como slice.
    spec = tmp_path / "spec.md"
    spec.write_text(
        "## Slices\n"
        "- [ ] slice-01 (x): Titulo\n"
        "- [ ] Step 1: no es una slice\n"
        "- [ ] una tarea suelta\n",
        encoding="utf-8",
    )
    slices = panel._parse_spec(spec)
    assert [s["slice_id"] for s in slices] == ["slice-01"]


def test_parse_spec_sin_name(panel: ModuleType, tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text("## Slices\n- [ ] slice-01: Sin nombre\n", encoding="utf-8")
    slices = panel._parse_spec(spec)
    assert slices[0]["slice_id"] == "slice-01"
    assert slices[0]["name"] == ""


def test_split_name(panel: ModuleType) -> None:
    assert panel._split_name("cantidad-vo") == "cantidad-vo"
    assert panel._split_name("refactor: extraer-repo") == "extraer-repo"
    assert panel._split_name(None) == ""
    assert panel._split_name("") == ""


def test_estado_de_fase_viva_manda_sobre_ledger(panel: ModuleType) -> None:
    slice_led = {"slice-01": {"estado": "hecha"}}
    spec_by_id = {"slice-01": {"box_estado": "pendiente"}}

    # Es la slice actual y esta esperando el merge -> esperando-merge, no "hecha".
    assert (
        panel._estado_de("slice-01", slice_led, spec_by_id, "slice-01", "waiting: merge", True)
        == "esperando-merge"
    )
    # Es la actual con una fase en curso (no esperando) -> en curso.
    assert (
        panel._estado_de("slice-01", slice_led, spec_by_id, "slice-01", "implement", False)
        == "en curso"
    )
    # No es la actual -> manda el ledger.
    assert (
        panel._estado_de("slice-01", slice_led, spec_by_id, "slice-99", "", False) == "hecha"
    )
    # Ni actual ni en ledger -> cae al estado de la spec (pendiente por defecto).
    assert panel._estado_de("slice-02", {}, spec_by_id, "slice-99", "", False) == "pendiente"


def test_resolve_spec_path(panel: ModuleType, tmp_path: Path) -> None:
    assert panel._resolve_spec_path(tmp_path, {}, "spec.md") == tmp_path / "spec.md"
    assert (
        panel._resolve_spec_path(tmp_path, {"spec_path": "sub/spec.md"}, None)
        == tmp_path / "sub/spec.md"
    )
    assert panel._resolve_spec_path(tmp_path, {}, None) is None
