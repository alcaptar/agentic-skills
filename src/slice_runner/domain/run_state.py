from __future__ import annotations

from enum import StrEnum


class RunState(StrEnum):
    OPEN = "open"
    MERGED = "merged"
    BLOCKED_CONTROLS = "blocked-controls"
    BLOCKED_HYGIENE = "blocked-hygiene"
    BLOCKED_VERIFY = "blocked-verify"
    BLOCKED_CI_RED = "blocked-ci-red"
    BLOCKED_CI_INDETERMINATE = "blocked-ci-indeterminate"
    BLOCKED_CI_CONFLICT = "blocked-ci-conflict"
    ABORTED_BUDGET = "aborted-budget"
    ABORTED_UNMEASURED_CALL = "aborted-unmeasured-call"
