from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.precheck_outcome import PrecheckOutcome

if TYPE_CHECKING:
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.sub_issue import SubIssue


class Prechecks:
    @classmethod
    def of(
        cls, *, subissue: SubIssue, parent: ParentIssue, branch_exists: bool, open_pull_request: int | None
    ) -> PrecheckOutcome:
        if subissue.state is IssueState.CLOSED:
            return PrecheckOutcome.SUBISSUE_ALREADY_CLOSED
        if open_pull_request is not None:
            return PrecheckOutcome.PULL_REQUEST_ALREADY_OPEN
        if branch_exists:
            return PrecheckOutcome.BRANCH_ALREADY_EXISTS
        if not parent.sources:
            return PrecheckOutcome.MISSING_SOURCES
        if not parent.controls.declared:
            return PrecheckOutcome.MISSING_CONTROLS

        return PrecheckOutcome.CLEAR
