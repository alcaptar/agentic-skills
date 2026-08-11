from __future__ import annotations

from enum import StrEnum


class RetryResponseKind(StrEnum):
    NOT_YET = "not-yet"
    RETRY = "retry"
