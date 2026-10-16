from __future__ import annotations

from enum import StrEnum


class FollowStanding(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    AWAITING_MERGE = "awaiting-merge"
    BLOCKED = "blocked"
    ABORTED = "aborted"
    MERGED = "merged"
