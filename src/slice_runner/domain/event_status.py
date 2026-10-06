from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from slice_runner.domain.run_state import RunState
from slice_runner.domain.waiting_on import WaitingOn

if TYPE_CHECKING:
    from slice_runner.domain.transition import Transition


class EventStatus(StrEnum):
    ADVANCING = "advancing"
    WAITING = "waiting"
    AWAITING_PERSON = "awaiting-person"
    CLOSED = "closed"
    NOTHING_TO_COMMIT = "nothing-to-commit"

    @classmethod
    def of_the_transition(cls, transition: Transition) -> EventStatus:
        if transition.state is not RunState.OPEN:
            return cls.CLOSED
        if transition.awaits_a_person:
            return cls.AWAITING_PERSON
        if transition.wait_seconds > 0:
            if WaitingOn.of_the_step(transition.run.step) is WaitingOn.PERSON:
                return cls.AWAITING_PERSON

            return cls.WAITING

        return cls.ADVANCING
