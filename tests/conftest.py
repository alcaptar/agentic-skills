"""Fixtures y helpers compartidos por la suite de `tests/`.

Antes cada fichero traia los suyos, y tres de ellos definian un `_write` con firmas
incompatibles: escribir un fichero, escribir un fichero **y** stagearlo, y serializar un log
JSON por lineas. Leer cualquier test obligaba a subir a la cabecera a averiguar cual era.
Aqui viven los que son de verdad comunes -escribir en un arbol y stagear-; lo que solo tiene
sentido en un fichero se queda alli, con un nombre que dice de que va.

`BASE_BRANCH`, `git` y el repo recien inicializado ya **no** se definen aqui: los comparte tambien el
arbol de test del programa (`src/slice_runner/tests/`), que no puede importar de este directorio, asi
que su origen unico es `src/slice_runner/tests/git_repo.py` y esto los consume.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.tests.git_repo import git, init_repo

if TYPE_CHECKING:
    from pathlib import Path


def escribe(root: Path, rel: str, content: str = "x") -> Path:
    """Escribe `root/rel` creando los directorios que hagan falta."""
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def stagea(repo: Path, rel: str, content: str = "x") -> None:
    """Escribe y stagea. `-f` porque algun test stagea rutas que un `.gitignore` real vetaria."""
    escribe(repo, rel, content)
    git(repo, "add", "-f", rel)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Repo git vacio con identidad y rama base deterministas."""
    return init_repo(tmp_path)
