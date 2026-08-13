from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.precheck_outcome import PrecheckOutcome

if TYPE_CHECKING:
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.sub_issue import SubIssue


class SourcesCheck(StrEnum):
    READABLE = "readable"
    UNREADABLE = "unreadable"
    OVER_BUDGET = "over-budget"


@dataclass(frozen=True, kw_only=True, slots=True)
class GroundSignals:
    branch_exists: bool
    open_pull_request: int | None
    sources_check: SourcesCheck


class Prechecks:
    @classmethod
    def of(
        cls, *, subissue: SubIssue, parent: ParentIssue, base_resolves_on_remote: bool, ground: GroundSignals
    ) -> PrecheckOutcome:
        of_the_subissue = cls.of_the_subissue(subissue)
        if of_the_subissue is not PrecheckOutcome.CLEAR:
            return of_the_subissue
        if not base_resolves_on_remote:
            return PrecheckOutcome.BASE_NOT_ON_REMOTE

        return cls._of_the_ground(parent=parent, ground=ground)

    @staticmethod
    def of_the_subissue(subissue: SubIssue) -> PrecheckOutcome:
        if subissue.repo is not None:
            return PrecheckOutcome.SLICE_IN_ANOTHER_REPO
        if subissue.state is IssueState.CLOSED:
            return PrecheckOutcome.SUBISSUE_ALREADY_CLOSED

        return PrecheckOutcome.CLEAR

    @classmethod
    def _of_the_ground(cls, *, parent: ParentIssue, ground: GroundSignals) -> PrecheckOutcome:
        if ground.open_pull_request is not None:
            return PrecheckOutcome.PULL_REQUEST_ALREADY_OPEN
        if ground.branch_exists:
            return PrecheckOutcome.BRANCH_ALREADY_EXISTS
        if not parent.sources:
            return PrecheckOutcome.MISSING_SOURCES
        of_the_sources = cls._of_the_sources_check(ground.sources_check)
        if of_the_sources is not PrecheckOutcome.CLEAR:
            return of_the_sources
        if not parent.controls.declared:
            return PrecheckOutcome.MISSING_CONTROLS

        return PrecheckOutcome.CLEAR

    @staticmethod
    def _of_the_sources_check(check: SourcesCheck) -> PrecheckOutcome:
        match check:
            case SourcesCheck.READABLE:
                return PrecheckOutcome.CLEAR
            case SourcesCheck.UNREADABLE:
                return PrecheckOutcome.UNREADABLE_SOURCE
            case SourcesCheck.OVER_BUDGET:
                return PrecheckOutcome.SOURCES_OVER_BUDGET
