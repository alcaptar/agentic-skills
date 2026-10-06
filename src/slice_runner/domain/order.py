from __future__ import annotations

from enum import StrEnum


class Order(StrEnum):
    GO = "go"
    REVIEW = "review"
    RETRY = "retry"
