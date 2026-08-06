from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step

if TYPE_CHECKING:
    from slice_runner.domain.transition import Transition


class EventStatus(StrEnum):
    ADVANCING = "advancing"
    WAITING = "waiting"
    AWAITING_PERSON = "awaiting-person"
    CLOSED = "closed"

    @classmethod
    def of_the_transition(cls, transition: Transition) -> EventStatus:
        if transition.state is not RunState.OPEN:
            return cls.CLOSED
        if transition.wait_seconds > 0:
            return cls.AWAITING_PERSON if transition.run.step is Step.AWAIT_MERGE else cls.WAITING

        return cls.ADVANCING
