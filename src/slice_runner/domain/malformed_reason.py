from __future__ import annotations

from enum import StrEnum


class MalformedReason(StrEnum):
    GO_CARRIES_TEXT = "go-carries-text"
    MISSING_CORRECTION = "missing-correction"
    MISSING_INSTRUCTION = "missing-instruction"
