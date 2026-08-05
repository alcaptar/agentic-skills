from __future__ import annotations

from dataclasses import replace

from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.sub_issue import SubIssue


class SubIssueMother:
    @staticmethod
    def pending() -> SubIssue:
        return SubIssue(
            number=45,
            slice_id="slice-05",
            title="slice-05 (prechecks-deterministas): comprobar antes de tocar codigo",
            state=IssueState.OPEN,
            repo=None,
            run=None,
            label=IssueLabel.PENDING,
        )

    @staticmethod
    def closed() -> SubIssue:
        return replace(SubIssueMother.pending(), state=IssueState.CLOSED)
