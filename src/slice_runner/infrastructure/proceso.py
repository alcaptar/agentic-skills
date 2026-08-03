"""Lanzar un proceso externo, detras de una abstraccion.

Es interno a la capa de infraestructura y no un puerto del dominio: el dominio no sabe que existan
procesos. Lo que compra es que los adaptadores que hablan con una linea de comandos se puedan
testear contra salidas grabadas sin lanzar nada.
"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class SalidaDeProceso:
    """Lo que dejo un proceso al terminar."""

    codigo: int
    stdout: str
    stderr: str


class Proceso(ABC):
    """Corre un comando con su entrada estandar y devuelve lo que dejo."""

    @abstractmethod
    def corre(self, argv: list[str], *, entrada: str) -> SalidaDeProceso:
        """Ejecuta `argv` pasandole `entrada` por entrada estandar."""


class ProcesoLocal(Proceso):
    """El proceso de verdad, en el anfitrion.

    Sin `check`: un codigo de salida distinto de cero es un dato que el adaptador interpreta -el
    harness escribe el motivo en stderr- y no una excepcion que borre el mensaje.
    """

    def corre(self, argv: list[str], *, entrada: str) -> SalidaDeProceso:
        acabado = subprocess.run(argv, input=entrada, capture_output=True, text=True, check=False)
        return SalidaDeProceso(codigo=acabado.returncode, stdout=acabado.stdout, stderr=acabado.stderr)
