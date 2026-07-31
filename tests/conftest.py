"""Fixtures y helpers compartidos por la suite.

Antes cada fichero traia los suyos, y tres de ellos definian un `_write` con firmas
incompatibles: escribir un fichero, escribir un fichero **y** stagearlo, y serializar un log
JSON por lineas. Leer cualquier test obligaba a subir a la cabecera a averiguar cual era.
Aqui viven los que son de verdad comunes -escribir en un arbol y hablar con `git`-; lo que
solo tiene sentido en un fichero se queda alli, con un nombre que dice de que va.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

RAMA_BASE = "master"
"""Rama base de los repos de prueba, fijada explicitamente.

`git init` la toma de `init.defaultBranch`, que es config de la maquina: sin esto, en un entorno
con `main` configurado el bloque de `diff-bundle` se cae -y su test de "la base no existe"
pasaria por el motivo equivocado, porque alli ninguna base existe-.
"""


def git(repo: Path, *args: str) -> None:
    """`git` en `repo`, silencioso y estricto: lo que falle aqui es un test mal montado."""
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


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
    git(tmp_path, "init", "-b", RAMA_BASE)
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "test")
    return tmp_path
