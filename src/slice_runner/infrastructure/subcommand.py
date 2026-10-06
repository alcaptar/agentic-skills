from __future__ import annotations

from enum import StrEnum


class Subcommand(StrEnum):
    VERIFY = "verify"
    EXPLAIN = "explain"
    RUN = "run"
    READ = "read"
    SPEND = "spend"
    DOCTOR = "doctor"
    METRICS = "metrics"
    RESET = "reset"
    STATUS = "status"
    FOLLOW = "follow"
    UNDERSTANDING = "understanding"
    GO = "go"
    REVIEW = "review"
    RETRY = "retry"
