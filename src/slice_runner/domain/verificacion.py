"""El puerto del juez adversarial y lo que hace falta para invocarlo.

Hay dos puertos separados para los agentes -este y el del implementador, que llega en su slice- y
no uno generico: "el que implementa no verifica" pasa asi a estar en los tipos, con firmas y
conjuntos de herramientas distintos, en vez de en la prosa de una skill.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.diff import DiffDeSlice
    from slice_runner.domain.veredicto import Veredicto


@dataclass(frozen=True, kw_only=True, slots=True)
class PeticionDeVerificacion:
    """Todo lo que el juez recibe: sus instrucciones, el repo que puede leer y el diff que juzga.

    Las instrucciones son un dato de la llamada y no un fichero que el adaptador busque por su
    cuenta, que es lo que las hace versionables y evaluables.
    """

    repo: str
    instrucciones: str
    diff: DiffDeSlice


class Verificador(ABC):
    """Puerto: juzga una slice ya implementada y devuelve su veredicto."""

    @abstractmethod
    def verifica(self, peticion: PeticionDeVerificacion) -> Veredicto:
        """Emite el veredicto, o levanta `VeredictoInvalidoError` si no hay ninguno utilizable."""
