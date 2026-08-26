from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.measurement import Measurement
from slice_runner.domain.run_state import RunState

if TYPE_CHECKING:
    from collections.abc import Sequence

    from slice_runner.domain.closed_slice_record import ClosedSliceRecord


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceRates:
    verifier_fail: Measurement
    blocked_by_controls: Measurement
    blocked_by_hygiene: Measurement
    first_attempt: Measurement
    implement_retries: Measurement
    verify_discards: Measurement
    ci_red: Measurement

    @classmethod
    def of(cls, records: Sequence[ClosedSliceRecord]) -> SliceRates:
        total = len(records)
        return cls(
            verifier_fail=Measurement.of_the_fraction(
                sum(1 for record in records if record.state == RunState.BLOCKED_VERIFY), total
            ),
            blocked_by_controls=Measurement.of_the_fraction(
                sum(1 for record in records if record.state == RunState.BLOCKED_CONTROLS), total
            ),
            blocked_by_hygiene=Measurement.of_the_fraction(
                sum(1 for record in records if record.state == RunState.BLOCKED_HYGIENE), total
            ),
            first_attempt=Measurement.of_the_fraction(sum(1 for record in records if record.first_attempt), total),
            implement_retries=Measurement.of_the_mean([float(record.implement_retries) for record in records]),
            verify_discards=Measurement.of_the_fraction(
                sum(1 for record in records if record.verify_discards > 0), total
            ),
            ci_red=Measurement.of_the_fraction(
                sum(1 for record in records if record.state == RunState.BLOCKED_CI_RED), total
            ),
        )
