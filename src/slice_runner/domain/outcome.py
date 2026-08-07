from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from slice_runner.domain.ci_status import CiStatus
from slice_runner.domain.control_status import ControlStatus
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.severity import Severity

if TYPE_CHECKING:
    from slice_runner.domain.control_outcome import ControlOutcome
    from slice_runner.domain.verdict import Verdict


class Outcome(StrEnum):
    DONE = "done"
    CORRECTIONS_ORDERED = "corrections-ordered"
    FAILED = "failed"
    HYGIENE_REJECTED = "hygiene-rejected"
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
                blocking = any(finding.severity is not Severity.LOW for finding in verdict.findings)

                return cls.CORRECTIONS_ORDERED if blocking else cls.DONE

    @classmethod
    def of_the_controls(cls, outcomes: tuple[ControlOutcome, ...]) -> Outcome:
        if any(outcome.status is ControlStatus.RED for outcome in outcomes):
            return cls.FAILED
        if any(outcome.status is ControlStatus.UNKNOWN for outcome in outcomes):
            return cls.INDETERMINATE

        return cls.DONE
