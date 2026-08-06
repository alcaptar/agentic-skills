from __future__ import annotations

from enum import StrEnum

from slice_runner.domain.exceptions import InvalidVerdictError, MeasuredCallError


class DiscardCause(StrEnum):
    INCOHERENT_VERDICT = "incoherent-verdict"
    FAILED_CALL = "failed-call"

    @classmethod
    def of_the_rejection(cls, rejection: MeasuredCallError) -> DiscardCause:
        if isinstance(rejection, InvalidVerdictError):
            return cls.INCOHERENT_VERDICT

        return cls.FAILED_CALL
