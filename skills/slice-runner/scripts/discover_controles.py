#!/usr/bin/env python3
"""Descubrimiento determinista de candidatos a control de un repo.

NO decide cuales son los controles del repo ni como se llaman: lista lo que el arbol de
ficheros deja ver -targets del `Makefile`, senales de `pyproject.toml`/`tox.ini`- para que
el agente lo filtre y la persona lo confirme. El juicio y la confirmacion no viven aqui;
este helper solo evita que el agente invente comandos o asuma un toolchain.

`slice-spec` compone: discover_candidates (aqui) -> el agente propone el mapeo
`nombre: comando` -> la persona confirma -> `issue_body.set_controles` escribe la seccion
`## Controles` del issue. A partir de ahi `slice-runner` solo lee: ningun agente vuelve a
abrir un `Makefile` en tiempo de run.

El `Makefile` va primero a proposito: en muchos repos todo corre en Docker via `make` y
lanzar `pytest`/`ruff`/`mypy` directos fallaria.

Determinista y offline: solo lee ficheros, no habla con `gh`. Se testea con un arbol de
prueba (tmp_path).
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

_TARGET_RE = re.compile(r"^([A-Za-z0-9][\w.-]*)\s*:(?!=)")
"""Un target de Makefile: empieza en columna 0 con alfanumerico y su `:` no es de `:=`.

Descartar el `:=` deja fuera las asignaciones de variable. Los targets ocultos (`.PHONY`) y las
reglas patron (`%.o: %.c`) tampoco matchean, porque no son cosas que se puedan invocar como
control.
"""

_COMMENT_RE = re.compile(r"^#+\s*(.*?)\s*$")
"""Comentario justo encima de un target: la pista de para que sirve."""

_PYPROJECT_SENALES = (
    ("ruff", ("tool", "ruff"), "ruff check ."),
    ("format", ("tool", "ruff", "format"), "ruff format --check ."),
    ("mypy", ("tool", "mypy"), "mypy ."),
    ("pytest", ("tool", "pytest", "ini_options"), "pytest"),
)
"""Senales en `pyproject.toml` y el comando que sugiere cada una.

El comando no se afina (rutas, flags, `uv run`): eso lo ajusta quien confirma, que es quien sabe.
"""


@dataclass(frozen=True, kw_only=True, slots=True)
class Candidato:
    """Un comando que el repo parece ofrecer como control.

    `nombre` es como lo llama el repo (el target, la herramienta), NO el nombre que tendra
    el control en el issue: eso lo decide quien confirma (un target `test` suele acabar
    declarado como control `tests`). `pista` es el comentario o la senal que lo justifica,
    para que el filtrado no sea a ciegas.
    """

    nombre: str
    comando: str
    fuente: str
    pista: str = ""


def _makefile_candidatos(makefile: Path) -> list[Candidato]:
    """Targets del Makefile, en orden de aparicion, con el comentario de encima como pista.

    Una linea de receta (la que empieza por tabulador) no reinicia la pista ni declara nada.
    """
    candidatos: list[Candidato] = []
    vistos: set[str] = set()
    pista = ""
    for raw in makefile.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith("\t"):
            continue
        if comentario := _COMMENT_RE.match(raw):
            pista = comentario.group(1)
            continue
        if m := _TARGET_RE.match(raw):
            nombre = m.group(1)
            if nombre not in vistos:
                vistos.add(nombre)
                candidatos.append(Candidato(nombre=nombre, comando=f"make {nombre}", fuente="makefile", pista=pista))
            pista = ""
            continue
        if not raw.strip():
            pista = ""
    return candidatos


def _pyproject_candidatos(pyproject: Path) -> list[Candidato]:
    """Senales de `pyproject.toml`: que herramientas de calidad tiene configuradas el repo.

    Un pyproject ilegible no es un error del descubrimiento: simplemente no aporta senales.
    Fallar aqui esconderia los candidatos del Makefile, que si valen.
    """
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return []

    candidatos: list[Candidato] = []
    for nombre, ruta, comando in _PYPROJECT_SENALES:
        nodo: object = data
        for clave in ruta:
            if not isinstance(nodo, dict) or clave not in nodo:
                nodo = None
                break
            nodo = nodo[clave]
        if nodo is not None:
            candidatos.append(
                Candidato(
                    nombre=nombre,
                    comando=comando,
                    fuente="pyproject",
                    pista=f"configurado en [{'.'.join(ruta)}]",
                )
            )
    return candidatos


def discover_candidates(repo_root: str | Path) -> list[Candidato]:
    """Lista candidatos a control: primero los targets del `Makefile`, luego las senales.

    Devolver un candidato no implica que sea un control: eso lo confirma la persona. Que la
    lista salga vacia tampoco significa que el repo no tenga controles -significa que hay que
    preguntarlo-, y un repo que de verdad no los tiene lo declara con `ninguno` en el issue.
    """
    root = Path(repo_root)
    candidatos: list[Candidato] = []

    makefile = next((root / n for n in ("Makefile", "makefile", "GNUmakefile") if (root / n).is_file()), None)
    if makefile is not None:
        candidatos += _makefile_candidatos(makefile)

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        candidatos += _pyproject_candidatos(pyproject)

    if (root / "tox.ini").is_file():
        candidatos.append(Candidato(nombre="tox", comando="tox", fuente="tox", pista="hay tox.ini"))

    return candidatos


def _format(candidatos: list[Candidato]) -> str:
    """Un candidato por linea, en la forma `nombre: comando` que espera la seccion del issue.

    La pista y la fuente van detras como comentario de Makefile, para que quien confirma decida
    con lo que justifica cada candidato delante.
    """
    lines = []
    for c in candidatos:
        sufijo = f"  # {c.pista} ({c.fuente})" if c.pista else f"  # ({c.fuente})"
        lines.append(f"{c.nombre}: {c.comando}{sufijo}")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Lista candidatos a control de un repo (no decide cuales lo son).")
    parser.add_argument("repo", nargs="?", default=".", help="raiz del repo (por defecto .)")
    args = parser.parse_args()
    print(_format(discover_candidates(args.repo)))
