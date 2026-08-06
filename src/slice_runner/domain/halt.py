from __future__ import annotations

from enum import StrEnum


class Halt(StrEnum):
    RUN_CLOSED = "run-closed"
    PRECHECKS_BLOCKED = "prechecks-blocked"
    AWAITING_ALIGNMENT = "awaiting-alignment"
    WAIT_EXHAUSTED = "wait-exhausted"
    PULL_REQUEST_CLOSED = "pull-request-closed"
