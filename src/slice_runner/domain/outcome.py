from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from slice_runner.domain.ci_status import CiStatus
from slice_runner.domain.ruling import Ruling

if TYPE_CHECKING:
    from slice_runner.domain.verdict import Verdict


class Outcome(StrEnum):
    DONE = "done"
    CORRECTIONS_ORDERED = "corrections-ordered"
    FAILED = "failed"
    PENDING = "pending"
    INDETERMINATE = "indeterminate"
    DISCARDED = "discarded"
    OVER_BUDGET = "over-budget"

    @classmethod
    def of_the_ci(cls, status: CiStatus) -> Outcome:
        match status:
            case CiStatus.GREEN:
                return cls.DONE
            case CiStatus.RED:
                return cls.FAILED
            case CiStatus.PENDING:
                return cls.PENDING
            case CiStatus.NO_CHECKS | CiStatus.UNKNOWN:
                return cls.INDETERMINATE

    @classmethod
    def of_the_verdict(cls, verdict: Verdict) -> Outcome:
        match verdict.ruling:
            case Ruling.FAIL:
                return cls.FAILED
            case Ruling.PASS:
                return cls.CORRECTIONS_ORDERED if verdict.findings else cls.DONE
