from __future__ import annotations

from enum import StrEnum


class ServerState(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
