from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class ServerWait:
    poll_seconds: float
    deadline_seconds: float
