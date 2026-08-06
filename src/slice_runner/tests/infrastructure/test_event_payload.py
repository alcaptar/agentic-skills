from __future__ import annotations

from slice_runner.infrastructure.event_payload import EventPayload
from slice_runner.tests.mothers.event_mother import EventMother


class TestWhatTheProgramEmits:
    def test_the_event_serialises_with_the_slice_the_step_the_instant_the_spend_and_the_status(self) -> None:
        assert EventPayload.from_domain(EventMother.advancing()).to_contract() == {
            "slice_id": "slice-05",
            "step": "run-controls",
            "at": "2024-01-01T12:30:45Z",
            "spend": {"cost_usd": 0.3433209, "turns": 9, "duration_ms": 36315, "calls": 1},
            "status": "advancing",
        }
