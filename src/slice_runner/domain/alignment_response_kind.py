from __future__ import annotations

from enum import StrEnum


class AlignmentResponseKind(StrEnum):
    NOT_YET = "not-yet"
    GO = "go"
    REVIEW = "review"
    MALFORMED = "malformed"
