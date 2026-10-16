from __future__ import annotations

from enum import StrEnum

from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure


class ClosedAs(StrEnum):
    OPEN = "open"
    MERGED = "merged"
    BLOCKED_CONTROLS = "blocked-controls"
    BLOCKED_HYGIENE = "blocked-hygiene"
    BLOCKED_VERIFY = "blocked-verify"
    BLOCKED_UNCHANGED_DIFF = "blocked-unchanged-diff"
    BLOCKED_CI_RED = "blocked-ci-red"
    BLOCKED_CI_INDETERMINATE = "blocked-ci-indeterminate"
    BLOCKED_CI_CONFLICT = "blocked-ci-conflict"
    BLOCKED_WORKTREE = "blocked-worktree"
    BLOCKED_LEFTOVER_WORKTREE = "blocked-leftover-worktree"
    ABORTED_BUDGET = "aborted-budget"
    ABORTED_UNMEASURED_CALL = "aborted-unmeasured-call"

    @classmethod
    def of(cls, closure: Closure) -> ClosedAs:
        return {closed.to_closure(): closed for closed in cls}[closure]

    def to_closure(self) -> Closure:
        return {
            ClosedAs.OPEN: Closure.open(),
            ClosedAs.MERGED: Closure.merged(),
            ClosedAs.BLOCKED_CONTROLS: Closure.because_of(ClosingReason.CONTROLS),
            ClosedAs.BLOCKED_HYGIENE: Closure.because_of(ClosingReason.HYGIENE),
            ClosedAs.BLOCKED_VERIFY: Closure.because_of(ClosingReason.VERIFY),
            ClosedAs.BLOCKED_UNCHANGED_DIFF: Closure.because_of(ClosingReason.UNCHANGED_DIFF),
            ClosedAs.BLOCKED_CI_RED: Closure.because_of(ClosingReason.CI_RED),
            ClosedAs.BLOCKED_CI_INDETERMINATE: Closure.because_of(ClosingReason.CI_INDETERMINATE),
            ClosedAs.BLOCKED_CI_CONFLICT: Closure.because_of(ClosingReason.CI_CONFLICT),
            ClosedAs.BLOCKED_WORKTREE: Closure.because_of(ClosingReason.WORKTREE),
            ClosedAs.BLOCKED_LEFTOVER_WORKTREE: Closure.because_of(ClosingReason.LEFTOVER_WORKTREE),
            ClosedAs.ABORTED_BUDGET: Closure.because_of(ClosingReason.BUDGET),
            ClosedAs.ABORTED_UNMEASURED_CALL: Closure.because_of(ClosingReason.UNMEASURED_CALL),
        }[self]
