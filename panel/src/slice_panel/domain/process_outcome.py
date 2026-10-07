from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class ProcessOutcome:
    exit_code: int
    stdout: str
    stderr: str
