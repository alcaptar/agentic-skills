from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.assignment import Assignment

if TYPE_CHECKING:
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.implementation import Implementation
    from slice_runner.domain.implementer import Implementer
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class ImplementSliceParams:
    worktree: str
    subissue: SubIssue
    parent: ParentIssue
    findings: tuple[Finding, ...] = ()


class ImplementSlice:
    def __init__(self, *, implementer: Implementer) -> None:
        self._implementer = implementer

    def execute(self, params: ImplementSliceParams) -> Implementation:
        return self._implementer.implement(self._assignment(params))

    @staticmethod
    def _assignment(params: ImplementSliceParams) -> Assignment:
        return Assignment(
            issue=params.subissue.number,
            slice_id=params.subissue.slice_id,
            repo=params.worktree,
            intention=params.subissue.intention,
            criteria=params.subissue.criteria,
            signal=params.subissue.signal,
            sources=params.parent.sources,
            controls=params.parent.controls,
            findings=params.findings,
        )
