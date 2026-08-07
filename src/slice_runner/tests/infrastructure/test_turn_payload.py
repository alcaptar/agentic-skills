from __future__ import annotations

from slice_runner.infrastructure.turn_payload import TurnPayload
from slice_runner.tests.mothers.turn_mother import TurnMother


class TestWhatTheProgramEmits:
    def test_the_turn_serialises_with_the_slice_the_step_and_the_number(self) -> None:
        assert TurnPayload.from_domain(TurnMother.first()).to_contract() == {
            "slice_id": "slice-05",
            "step": "implement",
            "number": 1,
        }
