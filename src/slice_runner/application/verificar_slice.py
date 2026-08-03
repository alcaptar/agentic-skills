"""Verificar una slice: dejar su diff en disco y llevarselo al juez adversarial."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.verificacion import PeticionDeVerificacion

if TYPE_CHECKING:
    from slice_runner.domain.diff import EmpaquetadorDeDiff
    from slice_runner.domain.veredicto import Veredicto
    from slice_runner.domain.verificacion import Verificador


@dataclass(frozen=True, kw_only=True, slots=True)
class VerificarSliceParams:
    """El repo y la base contra la que se diffea, mas las instrucciones que recibe el juez."""

    repo: str
    base: str
    instrucciones: str


class VerificarSlice:
    """Empaqueta el diff del indice contra la base y pide veredicto.

    El orden importa y es lo unico que este caso de uso decide: primero el bundle, porque un juez
    invocado sin diff da su veredicto sobre la nada y gasta la invocacion igual.
    """

    def __init__(self, *, empaquetador: EmpaquetadorDeDiff, verificador: Verificador) -> None:
        self._empaquetador = empaquetador
        self._verificador = verificador

    def execute(self, params: VerificarSliceParams) -> Veredicto:
        diff = self._empaquetador.empaqueta(repo=params.repo, base=params.base)
        return self._verificador.verifica(
            PeticionDeVerificacion(repo=params.repo, instrucciones=params.instrucciones, diff=diff)
        )
