from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    HERDR_MISSING = 1
    CLONE_UNKNOWN = 2
