from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.diff_stats import DiffStats


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceDiff:
    text: str
    files: tuple[str, ...]
    stats: DiffStats
