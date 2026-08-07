from __future__ import annotations

from slice_runner.domain.step import Step
from slice_runner.infrastructure.turn_log import HarnessTurn


class TurnMother:
    @staticmethod
    def first() -> HarnessTurn:
        return HarnessTurn(slice_id="slice-05", step=Step.IMPLEMENT, number=1)

    @staticmethod
    def second() -> HarnessTurn:
        return HarnessTurn(slice_id="slice-05", step=Step.IMPLEMENT, number=2)
