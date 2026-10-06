from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.corpus import JudgedRound
from slice_runner.tests.mothers.verdict_mother import VerdictMother

if TYPE_CHECKING:
    from slice_runner.domain.finding import Finding


class JudgedRoundMother:
    @staticmethod
    def of_the_round(round: int, *findings: Finding) -> JudgedRound:
        verdict = VerdictMother.failing(*findings) if findings else VerdictMother.passing()

        return JudgedRound(round=round, verdict=verdict)
