"""El diff de la slice, ya materializado en disco, y el puerto que lo produce."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, kw_only=True, slots=True)
class DiffDeSlice:
    """Rutas del bundle que el juez lee, y cuantos ficheros trae.

    Va por ruta y no por contenido a proposito: el juez lee el diff con `Read` desde su propio
    contexto, asi que meterlo aqui como cadena solo serviria para pasearlo por la memoria del
    programa.
    """

    slice_diff: Path
    files: Path
    n_ficheros: int


class EmpaquetadorDeDiff(ABC):
    """Puerto: deja en disco el diff de la slice contra su base."""

    @abstractmethod
    def empaqueta(self, *, repo: str, base: str) -> DiffDeSlice:
        """Materializa el diff, o levanta un `DiffNoEmpaquetableError` diciendo por que no hay."""


class DiffNoEmpaquetableError(ValueError):
    """No se pudo dejar un diff que verificar.

    Fail-closed: sin diff, el juez daria su veredicto sobre la nada. La familia se subdivide porque
    las dos causas no se arreglan igual, y quien las recibe -hoy la linea de comandos, manana el
    loop- decide cosas distintas con cada una.
    """


class IndiceVacioError(DiffNoEmpaquetableError):
    """El indice no traia nada respecto a la base: no hay cambio que juzgar.

    Es el sintoma de haberse olvidado el `git add`, porque lo que se empaqueta es el indice.
    """


class RepoOBaseNoResolubleError(DiffNoEmpaquetableError):
    """El repo o la base que se pidieron no resuelven, y no consta cual de los dos.

    Es un error de uso -`--base main` en un repo cuya rama es `master`, o una ruta de repo que no
    existe o no es un repo git-, no un indice vacio: el cambio puede estar entero y staged.
    Confundirlos manda a arreglar el codigo equivocado.

    Nombra los dos argumentos a proposito: quien produce el error no puede saber cual sobra, y un
    error que solo acusa a la base manda a corregir el flag que estaba bien.
    """
