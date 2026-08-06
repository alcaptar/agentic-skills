from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.checklist_entry import ChecklistEntry
from slice_runner.domain.exceptions import NoSliceLeftError
from slice_runner.domain.slice_queue import SliceQueue

if TYPE_CHECKING:
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.run_repository import RunRepository
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class SelectSliceParams:
    repo: str
    issue: int


@dataclass(frozen=True, kw_only=True, slots=True)
class SelectSliceResult:
    subissue: SubIssue
    parent: ParentIssue
    checklist: tuple[ChecklistEntry, ...]


class SelectSlice:
    def __init__(self, *, repository: RunRepository) -> None:
        self._repository = repository

    def execute(self, params: SelectSliceParams) -> SelectSliceResult:
        overview = self._repository.read_parent(repo=params.repo, issue=params.issue, slice_repo=None)
        children = self._repository.read_children(
            repo=params.repo, parent=params.issue, expected=overview.subissue_count
        )
        chosen = SliceQueue.next_in_line(children)
        if chosen is None:
            raise NoSliceLeftError(
                f"none of the {len(children)} slice(s) of issue {params.issue} can be run: "
                f"every one is closed, blocked or aborted"
            )

        return SelectSliceResult(
            subissue=chosen,
            parent=self._yardstick_of(chosen, overview=overview, params=params),
            checklist=tuple(ChecklistEntry.of(child) for child in children),
        )

    def _yardstick_of(self, chosen: SubIssue, *, overview: ParentIssue, params: SelectSliceParams) -> ParentIssue:
        if chosen.repo is None:
            return overview

        return self._repository.read_parent(repo=params.repo, issue=params.issue, slice_repo=chosen.repo)
