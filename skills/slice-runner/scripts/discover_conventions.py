#!/usr/bin/env python3
"""Descubrimiento determinista de candidatos a fuente de convencion en un repo.

NO decide cuales son convencion real: hace un glob amplio y devuelve candidatos (rutas
relativas) para que el agente los juzgue y el humano los confirme. El juicio y la
confirmacion no viven aqui; este helper solo evita que el agente invente rutas o asuma
una ubicacion fija (`docs/conventions/` + `CLAUDE.md`), que fue la causa raiz que este
mecanismo corrige.

`slice-spec` compone: discover_candidates (aqui) -> el agente filtra/propone -> el
humano confirma -> `issue_body.set_fuentes` escribe los punteros en el issue.

Determinista y offline: solo lee el arbol de ficheros, no habla con `gh`. Se testea con
un arbol de prueba (tmp_path).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from issue_body import Fuente, TipoFuente

_NOISE_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".idea",
        ".tox",
        ".eggs",
    }
)
"""Directorios que nunca contienen convenciones del repo: no se descienden."""

_DOC_FILENAMES = frozenset({"CLAUDE.md", "AGENTS.md", "GEMINI.md"})
_CONTRIBUTING_RE = re.compile(r"^contributing(\.md|\.rst|\.txt)?$", re.IGNORECASE)
"""Ficheros doc reconocibles por nombre (contexto/convencion a cualquier nivel)."""

_CONV_DIR_RE = re.compile(r"(convention|rules)", re.IGNORECASE)
"""Directorios cuyo nombre sugiere convencion declarativa."""

_SKILLS_DIR = ".claude/skills"
"""Nombre del contenedor de skills de proyecto."""


def _outermost(dirs: list[str]) -> list[str]:
    """Quita los directorios anidados dentro de otro ya presente (deja el mas externo)."""
    uniq = sorted(set(dirs))
    return [d for d in uniq if not any(d != other and d.startswith(other) for other in uniq)]


def discover_candidates(repo_root: str | Path) -> list[Fuente]:
    """Lista candidatos a fuente de convencion: docs (por orden de ruta) y luego skills.

    Rutas relativas a `repo_root`, en POSIX. Los directorios llevan `/` final. No decide:
    devolver un candidato no implica que sea convencion; eso lo confirma el humano.

    Las skills de proyecto son los hijos inmediatos de un `.claude/skills`, y los directorios
    ocultos de ahi dentro (p. ej. `.nwave`) se dejan fuera: son estado de herramienta, no
    skills. La poda de `dirnames` es in-place para que `os.walk` no descienda al ruido, y
    ordenada para que el recorrido sea estable.
    """
    root = Path(repo_root)
    docs: set[str] = set()
    skills: set[str] = set()
    conv_dirs: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _NOISE_DIRS)

        here = Path(dirpath)
        rel_here = here.relative_to(root).as_posix()

        if rel_here == _SKILLS_DIR or rel_here.endswith("/" + _SKILLS_DIR):
            for name in dirnames:
                if not name.startswith("."):
                    skills.add((here / name).relative_to(root).as_posix() + "/")

        if rel_here not in (".", "") and _CONV_DIR_RE.search(here.name):
            conv_dirs.append(rel_here + "/")

        for filename in filenames:
            if filename in _DOC_FILENAMES or _CONTRIBUTING_RE.match(filename):
                docs.add((here / filename).relative_to(root).as_posix())

    docs.update(_outermost(conv_dirs))

    doc_fuentes = [Fuente(tipo=TipoFuente.DOC, ruta=ruta) for ruta in sorted(docs)]
    skill_fuentes = [Fuente(tipo=TipoFuente.SKILL, ruta=ruta) for ruta in sorted(skills)]
    return doc_fuentes + skill_fuentes


def _format(fuentes: list[Fuente]) -> str:
    return "\n".join(f"{f.tipo}: {f.ruta}" for f in fuentes)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Lista candidatos a fuente de convencion de un repo (no decide).")
    parser.add_argument("repo", nargs="?", default=".", help="raiz del repo (por defecto .)")
    args = parser.parse_args()
    print(_format(discover_candidates(args.repo)))
