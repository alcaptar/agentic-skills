from __future__ import annotations

from enum import StrEnum


class RunState(StrEnum):
    OPEN = "open"
    MERGED = "merged"
    BLOCKED_CONTROLS = "blocked-controls"
    BLOCKED_HYGIENE = "blocked-hygiene"
    BLOCKED_VERIFY = "blocked-verify"
    BLOCKED_UNCHANGED_DIFF = "blocked-unchanged-diff"
    BLOCKED_CI_RED = "blocked-ci-red"
    BLOCKED_CI_INDETERMINATE = "blocked-ci-indeterminate"
    BLOCKED_CI_CONFLICT = "blocked-ci-conflict"
    ABORTED_BUDGET = "aborted-budget"
    ABORTED_UNMEASURED_CALL = "aborted-unmeasured-call"

    @property
    def publishes_the_findings(self) -> bool:
        match self:
            case RunState.BLOCKED_VERIFY | RunState.BLOCKED_UNCHANGED_DIFF:
                return True
            case (
                RunState.OPEN
                | RunState.MERGED
                | RunState.BLOCKED_CONTROLS
                | RunState.BLOCKED_HYGIENE
                | RunState.BLOCKED_CI_RED
                | RunState.BLOCKED_CI_INDETERMINATE
                | RunState.BLOCKED_CI_CONFLICT
                | RunState.ABORTED_BUDGET
                | RunState.ABORTED_UNMEASURED_CALL
            ):
                return False
