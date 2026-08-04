from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from controles import MotivoSinBundle, escribe_diff_bundle
from slice_runner.domain.diff import (
    DiffBundler,
    DiffNotBundlableError,
    EmptyIndexError,
    SliceDiff,
    UnresolvableRepoOrBaseError,
)

if TYPE_CHECKING:
    from controles import ResultadoBundle


class GitDiffBundler(DiffBundler):
    def __init__(self, *, destination: Path) -> None:
        self._destination = destination

    def bundle(self, *, repo: str, base: str) -> SliceDiff:
        result = escribe_diff_bundle(repo, base, str(self._destination))
        if not result.passed:
            raise self._failure_of(result)
        return SliceDiff(
            slice_diff=Path(result.slice_diff),
            files=Path(result.files),
            n_files=result.n_files,
        )

    @staticmethod
    def _failure_of(result: ResultadoBundle) -> DiffNotBundlableError:
        detail = "; ".join(result.hallazgos)
        if result.motivo is MotivoSinBundle.REPO_O_BASE_NO_RESOLUBLE:
            return UnresolvableRepoOrBaseError(detail)
        if result.motivo is MotivoSinBundle.INDICE_VACIO:
            return EmptyIndexError(detail)
        return DiffNotBundlableError(detail)
