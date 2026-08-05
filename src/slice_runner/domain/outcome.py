from __future__ import annotations

from enum import StrEnum


class Outcome(StrEnum):
    DONE = "done"
    CORRECTIONS_ORDERED = "corrections-ordered"
    FAILED = "failed"
    PENDING = "pending"
    INDETERMINATE = "indeterminate"
    DISCARDED = "discarded"
    OVER_BUDGET = "over-budget"
