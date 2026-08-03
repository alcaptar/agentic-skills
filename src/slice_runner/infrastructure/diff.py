"""Adaptador del empaquetador de diffs sobre el `diff-bundle` que ya existia.

La logica de que rango se diffea -el indice contra el branch-point, con `--merge-base`- y por que,
vive en `controles.escribe_diff_bundle` con sus tests. Aqui no se reimplementa: se traduce su
resultado -y, cuando no hay bundle, la causa- a los tipos del dominio, que es lo unico que el
programa necesita de mas.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from controles import MotivoSinBundle, escribe_diff_bundle
from slice_runner.domain.diff import (
    DiffDeSlice,
    DiffNoEmpaquetableError,
    EmpaquetadorDeDiff,
    IndiceVacioError,
    RepoOBaseNoResolubleError,
)

if TYPE_CHECKING:
    from controles import ResultadoBundle


def _error_de(resultado: ResultadoBundle) -> DiffNoEmpaquetableError:
    """Traduce el motivo del control al error del dominio que le corresponde.

    Se ramifica por el motivo y no por el texto de los hallazgos: ese texto es para quien lo lee, y
    decidir con una subcadena es como un `--base` mal escrito acaba contado como indice vacio.
    """
    detalle = "; ".join(resultado.hallazgos)
    if resultado.motivo is MotivoSinBundle.REPO_O_BASE_NO_RESOLUBLE:
        return RepoOBaseNoResolubleError(detalle)
    if resultado.motivo is MotivoSinBundle.INDICE_VACIO:
        return IndiceVacioError(detalle)
    return DiffNoEmpaquetableError(detalle)


class EmpaquetadorGit(EmpaquetadorDeDiff):
    """Materializa `slice.diff` y `files.txt` en `destino`."""

    def __init__(self, *, destino: Path) -> None:
        self._destino = destino

    def empaqueta(self, *, repo: str, base: str) -> DiffDeSlice:
        resultado = escribe_diff_bundle(repo, base, str(self._destino))
        if not resultado.passed:
            raise _error_de(resultado)
        return DiffDeSlice(
            slice_diff=Path(resultado.slice_diff),
            files=Path(resultado.files),
            n_ficheros=resultado.n_files,
        )
