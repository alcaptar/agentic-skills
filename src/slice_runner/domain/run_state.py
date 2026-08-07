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
    ABORTED_BUDGET = "aborted-budget"
