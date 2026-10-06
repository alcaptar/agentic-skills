from __future__ import annotations

from enum import StrEnum


class EventStatus(StrEnum):
    ADVANCING = "advancing"
    WAITING = "waiting"
    AWAITING_PERSON = "awaiting-person"
    CLOSED = "closed"
    NOTHING_TO_COMMIT = "nothing-to-commit"
