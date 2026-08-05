from __future__ import annotations

from enum import StrEnum


class DiscardCause(StrEnum):
    INCOHERENT_VERDICT = "incoherent-verdict"
    FAILED_CALL = "failed-call"
