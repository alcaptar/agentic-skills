from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.closing_worktree import ClosingWorktree
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step
from slice_runner.domain.worktree_retirement import WorktreeRetirement

if TYPE_CHECKING:
    from slice_runner.domain.run import Run


class WorktreeRetirementPolicy:
    @classmethod
    def of_the_closing(cls, *, state: RunState, step: Step) -> ClosingWorktree:
        match state:
            case RunState.MERGED:
                return ClosingWorktree.RETIRE
            case RunState.ABORTED_BUDGET | RunState.ABORTED_UNMEASURED_CALL:
                return cls._of_the_aborted(step)
            case RunState.BLOCKED_WORKTREE:
                return ClosingWorktree.NOT_OURS
            case RunState.BLOCKED_LEFTOVER_WORKTREE:
                return ClosingWorktree.UNEXPECTED
            case (
                RunState.OPEN
                | RunState.BLOCKED_CONTROLS
                | RunState.BLOCKED_HYGIENE
                | RunState.BLOCKED_VERIFY
                | RunState.BLOCKED_UNCHANGED_DIFF
                | RunState.BLOCKED_CI_RED
                | RunState.BLOCKED_CI_INDETERMINATE
                | RunState.BLOCKED_CI_CONFLICT
            ):
                return ClosingWorktree.KEEP_FOR_RESUMING

    @classmethod
    def of(cls, *, uncommitted: bool, local_only_commits: int) -> WorktreeRetirement:
        if uncommitted:
            return WorktreeRetirement.KEPT_UNCOMMITTED_WORK
        if local_only_commits > 0:
            return WorktreeRetirement.KEPT_LOCAL_ONLY_COMMITS

        return WorktreeRetirement.RETIRED

    @classmethod
    def expects_a_tree(cls, *, label: IssueLabel | None, run: Run | None) -> bool:
        if label is IssueLabel.AWAITING_ALIGNMENT:
            return True
        if run is None:
            return False
        closed = label.closed_as if label is not None else None
        if closed is None:
            return True

        match cls.of_the_closing(state=closed, step=run.step):
            case ClosingWorktree.RETIRE | ClosingWorktree.UNEXPECTED:
                return False
            case ClosingWorktree.KEEP_FOR_RESUMING | ClosingWorktree.NOT_OURS:
                return True

    @staticmethod
    def _of_the_aborted(step: Step) -> ClosingWorktree:
        match step:
            case Step.MOUNT_WORKTREE | Step.UNDERSTAND:
                return ClosingWorktree.RETIRE
            case (
                Step.IMPLEMENT
                | Step.RUN_CONTROLS
                | Step.VERIFY
                | Step.OPEN_PULL_REQUEST
                | Step.AWAIT_CI
                | Step.CATCH_UP
                | Step.AWAIT_MERGE
            ):
                return ClosingWorktree.KEEP_FOR_RESUMING
