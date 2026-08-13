#!/usr/bin/env python3
"""Descubrimiento determinista de trabajo previo y piezas reutilizables en un repo.

NO decide que es relevante: busca por los terminos que se le den y devuelve candidatos
-pull requests mergeadas, issues cerradas y ficheros que ya nombran el concepto- para que
el agente los juzgue y el humano los confirme. El juicio y la confirmacion no viven aqui.

Existe porque `slice-spec` troceaba sin mirar que habia ya. Dos casos reales del
2026-08-13: se propuso una slice para implementar un `type` del titulo que ningun consumidor
leia -lo correcto era retirarlo-, y otra tradujo el vocabulario de un script que una tercera
estaba jubilando. Las dos se evitan con la misma pregunta: quien consume esto y que hay ya.

`slice-spec` compone: discover_prior_art (aqui) -> el agente filtra/propone -> el humano
confirma -> la seccion `## Lo que ya existe` se escribe en el issue padre.

A diferencia de `discover_conventions.py`, este **si** habla con `gh`, porque el registro de
lo que se intento antes son las pull requests mergeadas y las issues cerradas. Sin `gh`
utilizable devuelve solo los candidatos del arbol de ficheros y lo dice, en vez de fallar:
media respuesta acotada vale mas que ninguna.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

TOPE_SEGUNDOS = 60
"""Tope por llamada a `gh`, como exige el invariante de procesos externos del repo."""

MAXIMO_POR_CLASE = 8
"""Cuantos candidatos se devuelven de cada clase. Acota la arqueologia: veinte lineas, no un informe."""

EXTENSIONES = (".py", ".md", ".ts", ".tsx", ".js", ".go", ".rb", ".java", ".kt", ".sql", ".yaml", ".yml")

_IGNORADOS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache"}


class TipoHallazgo(StrEnum):
    """`pieza` es codigo que ya existe; `precedente`, trabajo previo que alguien ya hizo o intento."""

    PIEZA = "pieza"
    PRECEDENTE = "precedente"


@dataclass(frozen=True, kw_only=True, slots=True)
class Hallazgo:
    """Un candidato a tener en cuenta antes de trocear.

    `referencia` es una ruta relativa al repo (para una pieza) o `#numero` (para un precedente),
    de modo que siempre se pueda comprobar. `detalle` es lo que se vio, no una conclusion.
    """

    tipo: TipoHallazgo
    referencia: str
    detalle: str


class Precedentes:
    """Lo que ya se intento: pull requests mergeadas e issues cerradas que casan con los terminos."""

    @staticmethod
    def _gh(argv: list[str]) -> list[dict[str, object]]:
        try:
            hecho = subprocess.run(argv, capture_output=True, text=True, timeout=TOPE_SEGUNDOS, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return []
        if hecho.returncode != 0:
            return []
        try:
            cargado = json.loads(hecho.stdout)
        except json.JSONDecodeError:
            return []

        return cargado if isinstance(cargado, list) else []

    @classmethod
    def buscar(cls, repo: str, terminos: list[str]) -> list[Hallazgo]:
        consulta = " OR ".join(terminos)
        hallazgos: list[Hallazgo] = []
        for argv, etiqueta in (
            (
                [
                    "gh",
                    "pr",
                    "list",
                    "--repo",
                    repo,
                    "--state",
                    "merged",
                    "--search",
                    consulta,
                    "--limit",
                    str(MAXIMO_POR_CLASE),
                    "--json",
                    "number,title",
                ],
                "pull request mergeada",
            ),
            (
                [
                    "gh",
                    "issue",
                    "list",
                    "--repo",
                    repo,
                    "--state",
                    "closed",
                    "--search",
                    consulta,
                    "--limit",
                    str(MAXIMO_POR_CLASE),
                    "--json",
                    "number,title",
                ],
                "issue cerrada",
            ),
        ):
            for fila in cls._gh(argv):
                numero = fila.get("number")
                titulo = fila.get("title")
                if isinstance(numero, int) and isinstance(titulo, str):
                    hallazgos.append(
                        Hallazgo(tipo=TipoHallazgo.PRECEDENTE, referencia=f"#{numero}", detalle=f"{etiqueta}: {titulo}")
                    )

        return hallazgos


class Piezas:
    """Codigo que ya nombra el concepto: los ficheros donde aparece alguno de los terminos."""

    @classmethod
    def buscar(cls, raiz: str, terminos: list[str]) -> list[Hallazgo]:
        patron = re.compile("|".join(re.escape(t) for t in terminos), re.IGNORECASE)
        contados: dict[str, int] = {}
        root = Path(raiz).resolve()
        for camino in root.rglob("*"):
            if not camino.is_file() or camino.suffix not in EXTENSIONES:
                continue
            if any(parte in _IGNORADOS for parte in camino.parts):
                continue
            try:
                texto = camino.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            aciertos = len(patron.findall(texto))
            if aciertos:
                contados[camino.relative_to(root).as_posix()] = aciertos

        ordenados = sorted(contados.items(), key=lambda par: (-par[1], par[0]))[:MAXIMO_POR_CLASE]

        return [
            Hallazgo(tipo=TipoHallazgo.PIEZA, referencia=ruta, detalle=f"{aciertos} mencion(es)")
            for ruta, aciertos in ordenados
        ]


def discover_prior_art(raiz: str, repo: str | None, terminos: list[str]) -> list[Hallazgo]:
    """Devuelve candidatos de las dos clases. Sin `repo` no busca precedentes, solo piezas."""
    piezas = Piezas.buscar(raiz, terminos)
    precedentes = Precedentes.buscar(repo, terminos) if repo else []

    return precedentes + piezas


def _format(hallazgos: list[Hallazgo]) -> str:
    if not hallazgos:
        return "sin candidatos: ni el arbol ni el historial nombran esos terminos"

    return "\n".join(f"{h.tipo}: {h.referencia} - {h.detalle}" for h in hallazgos)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Lista trabajo previo y piezas reutilizables de un repo (no decide).")
    parser.add_argument("terminos", nargs="+", help="terminos del concepto que se va a trocear")
    parser.add_argument("--raiz", default=".", help="raiz del repo (por defecto .)")
    parser.add_argument("--repo", default=None, help="repo de GitHub como org/repo, para buscar precedentes")
    args = parser.parse_args()
    print(_format(discover_prior_art(args.raiz, args.repo, args.terminos)))
