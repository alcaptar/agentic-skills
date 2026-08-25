from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.source import Source


@dataclass(frozen=True, kw_only=True, slots=True)
class MergeConflict:
    repo: str
    issue: int
    slice_id: str
    worktree: str
    branch: str
    base: str
    conflicted_paths: tuple[str, ...]
    sources: tuple[Source, ...]
