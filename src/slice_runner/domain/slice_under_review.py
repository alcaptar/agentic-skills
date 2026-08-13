from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.checklist_entry import ChecklistEntry
    from slice_runner.domain.slice_diff import SliceDiff
    from slice_runner.domain.source import Source


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceUnderReview:
    slice_id: str
    repo: str
    issue: int
    worktree: str
    diff: SliceDiff
    prior_art: str
    signal: str
    criteria: tuple[str, ...]
    sources: tuple[Source, ...]
    checklist: tuple[ChecklistEntry, ...]
