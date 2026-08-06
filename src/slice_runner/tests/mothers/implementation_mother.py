from __future__ import annotations

from slice_runner.domain.implementation import Implementation
from slice_runner.tests.mothers.reported_path_mother import ReportedPathMother


class ImplementationMother:
    @staticmethod
    def of_two_paths() -> Implementation:
        return Implementation(
            paths=(ReportedPathMother.production_file(), ReportedPathMother.test_file()),
            left_out="nothing was left out",
            cost_usd=0.3433209,
            turns=9,
        )
