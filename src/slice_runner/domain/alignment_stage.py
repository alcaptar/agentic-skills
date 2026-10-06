from __future__ import annotations

from enum import StrEnum


class AlignmentStage(StrEnum):
    DRAFT = "draft"
    AWAITING = "awaiting"
    AGREED = "agreed"
