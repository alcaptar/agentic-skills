from __future__ import annotations

from enum import StrEnum


class CheckVerdict(StrEnum):
    READY = "ready"
    MISSING = "missing"
