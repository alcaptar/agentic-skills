from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from slice_runner.domain.issue_label import IssueLabel

if TYPE_CHECKING:
    from slice_runner.domain.closure import Closure
    from slice_runner.domain.step import Step


class FollowStanding(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    AWAITING_MERGE = "awaiting-merge"
    BLOCKED = "blocked"
    ABORTED = "aborted"
    MERGED = "merged"

    @classmethod
    def of(cls, *, closure: Closure, step: Step | None) -> FollowStanding:
        label = IssueLabel.of(closure=closure, step=step)
        if label is None:
            return cls.MERGED

        return cls._of_the_label(label)

    @classmethod
    def _of_the_label(cls, label: IssueLabel) -> FollowStanding:
        match label:
            case IssueLabel.PENDING:
                return cls.PENDING
            case IssueLabel.IN_PROGRESS:
                return cls.IN_PROGRESS
            case IssueLabel.AWAITING_MERGE:
                return cls.AWAITING_MERGE
            case (
                IssueLabel.BLOCKED_CONTROLS
                | IssueLabel.BLOCKED_JUDGE
                | IssueLabel.BLOCKED_CI_RED
                | IssueLabel.BLOCKED_CI_INDETERMINATE
                | IssueLabel.BLOCKED_CI_CONFLICT
                | IssueLabel.BLOCKED_WORKTREE
            ):
                return cls.BLOCKED
            case IssueLabel.ABORTED_BUDGET | IssueLabel.ABORTED_UNMEASURED_CALL:
                return cls.ABORTED
