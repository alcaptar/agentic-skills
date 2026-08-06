from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.issue_state import IssueState

if TYPE_CHECKING:
    from slice_runner.domain.sub_issue import SubIssue


class SliceQueue:
    @classmethod
    def next_in_line(cls, children: tuple[SubIssue, ...]) -> SubIssue | None:
        for child in children:
            if cls.runnable(child):
                return child

        return None

    @classmethod
    def find(cls, children: tuple[SubIssue, ...], slice_id: str) -> SubIssue | None:
        for child in children:
            if child.slice_id == slice_id:
                return child

        return None

    @classmethod
    def runnable(cls, child: SubIssue) -> bool:
        return child.state is IssueState.OPEN and not cls._disqualifying(child.label)

    @staticmethod
    def _disqualifying(label: IssueLabel | None) -> bool:
        match label:
            case None | IssueLabel.PENDING | IssueLabel.IN_PROGRESS | IssueLabel.AWAITING_MERGE:
                return False
            case (
                IssueLabel.AWAITING_ALIGNMENT
                | IssueLabel.BLOCKED_CONTROLS
                | IssueLabel.BLOCKED_VERIFY
                | IssueLabel.BLOCKED_CI_RED
                | IssueLabel.BLOCKED_CI_INDETERMINATE
                | IssueLabel.ABORTED_BUDGET
            ):
                return True
