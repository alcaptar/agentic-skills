from __future__ import annotations

from enum import StrEnum


class ConflictBlockCause(StrEnum):
    TREE_STILL_CONFLICTED = "tree-still-conflicted"
    CONTROLS_FAILED = "controls-failed"
