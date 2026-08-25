from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.assignment import Assignment

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.diff_reader import DiffReader
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.implementation import Implementation
    from slice_runner.domain.implementer import Implementer
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.requested_change import RequestedChange
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class ImplementSliceParams:
    repo: str
    worktree: str
    subissue: SubIssue
    parent: ParentIssue
    findings: tuple[Finding, ...] = ()
    control_logs: tuple[Path, ...] = ()
    hygiene_refusal: str = ""
    understanding: str = ""
    retry_instruction: str = ""
    requested_changes: tuple[RequestedChange, ...] = ()
    previous_call_died: bool = False


class ImplementSlice:
    def __init__(self, *, implementer: Implementer, reader: DiffReader) -> None:
        self._implementer = implementer
        self._reader = reader

    def execute(self, params: ImplementSliceParams) -> Implementation:
        return self._implementer.implement(self._assignment(params))

    def _assignment(self, params: ImplementSliceParams) -> Assignment:
        return Assignment(
            issue=params.subissue.number,
            slice_id=params.subissue.slice_id.canonical,
            repo=params.repo,
            worktree=params.worktree,
            intention=params.subissue.intention,
            prior_art=params.parent.prior_art,
            criteria=params.subissue.criteria,
            signal=params.subissue.signal,
            excludes=params.subissue.excludes,
            replaces=params.subissue.replaces,
            sources=params.parent.sources,
            controls=params.parent.controls,
            findings=params.findings,
            control_logs=params.control_logs,
            hygiene_refusal=params.hygiene_refusal,
            understanding=params.understanding,
            retry_instruction=params.retry_instruction,
            requested_changes=params.requested_changes,
            dirty_worktree_files=self._dirty_worktree_files(params),
        )

    def _dirty_worktree_files(self, params: ImplementSliceParams) -> tuple[str, ...]:
        if not params.previous_call_died:
            return ()

        return self._reader.dirty(worktree=params.worktree)
