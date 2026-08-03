from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceDiff:
    slice_diff: Path
    files: Path
    n_files: int


class DiffBundler(ABC):
    @abstractmethod
    def bundle(self, *, repo: str, base: str) -> SliceDiff: ...


class DiffNotBundlableError(ValueError):
    pass


class EmptyIndexError(DiffNotBundlableError):
    pass


class UnresolvableRepoOrBaseError(DiffNotBundlableError):
    pass
