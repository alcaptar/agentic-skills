from __future__ import annotations

from enum import IntEnum

from slice_runner.domain.ruling import Ruling


class ExitCode(IntEnum):
    PASS = 0
    FAIL = 1
    NO_USABLE_VERDICT = 2
    NO_DIFF = 3
    USAGE_ERROR = 4

    @classmethod
    def of(cls, ruling: Ruling) -> ExitCode:
        match ruling:
            case Ruling.PASS:
                return cls.PASS
            case Ruling.FAIL:
                return cls.FAIL
