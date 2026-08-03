"""Repos git de prueba: la rama base, el `git` silencioso y el arbol recien inicializado.

Origen unico de los tres para **los dos** arboles de test. `tests/conftest.py` los importa de aqui,
y la direccion es esta y no la inversa porque `src` entra en el `pythonpath` y el directorio de
`conftest` solo esta importable desde si mismo: `slice_runner.tests` es el unico de los dos lados
que el otro puede leer.

Estaban escritos dos veces -dos `RAMA_BASE` y dos primitivas de `git`-, que es el modo de fallo por
el que `CLAUDE.md` prohibe redefinir lo compartido: divergen sin que nada falle, y la que divergia
aqui decide en que rama nace cada repo de prueba.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

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


def inicializa_repo(raiz: Path) -> Path:
    """Deja en `raiz` un repo git vacio con identidad y rama base deterministas.

    Crea el directorio si no existe, porque `git init` exige que ya este: los dos usos son un
    `tmp_path` que ya existe y un subdirectorio suyo que no.
    """
    raiz.mkdir(parents=True, exist_ok=True)
    git(raiz, "init", "-b", RAMA_BASE)
    git(raiz, "config", "user.email", "t@example.com")
    git(raiz, "config", "user.name", "test")
    return raiz
