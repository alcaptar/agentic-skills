"""Fixtures compartidas de los tests de los scripts deterministas.

`gates.py` y `metrics.py` se importan por nombre (pythonpath en pyproject). El panel
vive en `panel/slice-panel.py` (fichero con guion, no importable por nombre): se carga
con `importlib` y se expone como fixture de sesion.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PANEL_PATH = _REPO_ROOT / "panel" / "slice-panel.py"


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def panel() -> ModuleType:
    """El modulo del panel (panel/slice-panel.py), cargado por path."""
    return _load_module("slice_panel", _PANEL_PATH)
