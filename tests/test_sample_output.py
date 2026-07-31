"""El ejemplo de salida del smoke, medido con la vara con la que el smoke mide.

`smoke/sample-output/*.example` es la referencia de "esto es lo que la slice deberia producir", y
`smoke/fixture/` es el proyecto donde la produce, con su propio ruleset de ruff -el mismo del repo
raiz a proposito, para que el smoke mida al runner contra una vara realista-. Nada ataba las dos
cosas: el ejemplo llevaba dos `pytest.raises(ValueError)` sin `match=`, que `PT011` rechaza, asi
que copiarlo tal cual dejaba `make -C smoke/fixture linting` en rojo. Quien lo usara de plantilla
escribia codigo que el propio smoke rechaza, y eso solo se veia en el siguiente smoke.

El test no lee el texto del ejemplo buscando `match=`: lo instala en su sitio dentro de una copia
de la fixture y corre alli el mismo ruff que corre `make linting`. Asi cae sobre el ejemplo
cualquier regla del ruleset, no solo la que hoy estaba incumplida.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE = _ROOT / "smoke" / "fixture"
_SAMPLE_OUTPUT = _ROOT / "smoke" / "sample-output"

_DESTINO_EN_LA_FIXTURE = {
    "core.py.example": "fizzbuzz/core.py",
    "test_core.py.example": "tests/test_core.py",
}
"""Donde acaba cada ejemplo cuando es codigo de la fixture, segun `smoke/fixture/spec.md`."""

_LINTING = {
    "check-style": ("check", "."),
    "check-format": ("format", "--check", "."),
}
"""Los dos targets de los que `make linting` se compone en `smoke/fixture/Makefile`."""


@pytest.fixture
def fixture_con_el_ejemplo_instalado(tmp_path: Path) -> Path:
    """Copia de la fixture reducida a lo que ruff lee: su config y los ejemplos en su sitio.

    Se copia en vez de linterar `smoke/sample-output/` en su sitio porque el `.example` no es un
    `.py` -ruff ni lo mira- y porque las exenciones por fichero de la fixture (`tests/*`) se
    resuelven contra la raiz del proyecto, o sea que el ejemplo solo se mide de verdad desde la
    ruta en la que el runner lo escribe.
    """
    shutil.copy(_FIXTURE / "pyproject.toml", tmp_path / "pyproject.toml")
    for ejemplo, destino in _DESTINO_EN_LA_FIXTURE.items():
        ruta = tmp_path / destino
        ruta.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(_SAMPLE_OUTPUT / ejemplo, ruta)
    return tmp_path


@pytest.mark.parametrize("target", sorted(_LINTING))
def test_el_ejemplo_pasa_el_linting_de_la_fixture(target: str, fixture_con_el_ejemplo_instalado: Path) -> None:
    """Cada mitad de `make -C smoke/fixture linting` sale con 0 sobre el ejemplo instalado."""
    resultado = subprocess.run(
        [sys.executable, "-m", "ruff", *_LINTING[target]],
        cwd=fixture_con_el_ejemplo_instalado,
        capture_output=True,
        text=True,
        check=False,
    )

    assert resultado.returncode == 0, (
        f"`make -C smoke/fixture {target}` rechazaria el ejemplo de smoke/sample-output/, "
        f"asi que la referencia que el harness ofrece no pasa la vara con la que el harness "
        f"mide:\n{resultado.stdout}{resultado.stderr}"
    )
