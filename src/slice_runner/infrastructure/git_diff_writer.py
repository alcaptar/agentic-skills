from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from controles import MotivoSinBundle, escribe_diff_bundle
from slice_runner.domain.diff_on_disk import DiffOnDisk
from slice_runner.domain.diff_writer import DiffWriter
from slice_runner.domain.exceptions import DiffNotWrittenError, EmptyIndexError, UnresolvableRepoOrBaseError

if TYPE_CHECKING:
    from controles import ResultadoBundle


class GitDiffWriter(DiffWriter):
    def __init__(self, *, destination: Path) -> None:
        self._destination = destination

    def write(self, *, repo: str, base: str) -> DiffOnDisk:
        result = escribe_diff_bundle(repo, base, str(self._destination))
        if not result.passed:
            raise self._failure_of(result)

        return DiffOnDisk(
            diff=Path(result.slice_diff),
            files=Path(result.files),
            n_files=result.n_files,
        )

    @staticmethod
    def _failure_of(result: ResultadoBundle) -> DiffNotWrittenError:
        detail = "; ".join(result.hallazgos)
        if result.motivo is MotivoSinBundle.REPO_O_BASE_NO_RESOLUBLE:
            return UnresolvableRepoOrBaseError(detail)
        if result.motivo is MotivoSinBundle.INDICE_VACIO:
            return EmptyIndexError(detail)

        return DiffNotWrittenError(detail)
