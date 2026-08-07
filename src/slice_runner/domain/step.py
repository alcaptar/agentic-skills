from __future__ import annotations

from enum import StrEnum


class Step(StrEnum):
    UNDERSTAND = "understand"
    IMPLEMENT = "implement"
    RUN_CONTROLS = "run-controls"
    VERIFY = "verify"
    OPEN_PULL_REQUEST = "open-pull-request"
    AWAIT_CI = "await-ci"
    AWAIT_MERGE = "await-merge"
