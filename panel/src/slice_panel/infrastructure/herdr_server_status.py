from __future__ import annotations

from typing import ClassVar

from slice_panel.domain.server_state import ServerState
from slice_panel.infrastructure.herdr_payload_rejected import HerdrPayloadRejectedError


class HerdrServerStatus:
    KEY: ClassVar[str] = "status"
    RUNNING: ClassVar[str] = "running"
    STOPPED: ClassVar[str] = "not running"

    @classmethod
    def state_of(cls, text: str) -> ServerState:
        for line in text.splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip() == cls.KEY:
                return cls._classified(value.strip())

        raise HerdrPayloadRejectedError("herdr answered the server status without a `status:` line")

    @classmethod
    def _classified(cls, value: str) -> ServerState:
        if value == cls.RUNNING:
            return ServerState.RUNNING
        if value == cls.STOPPED:
            return ServerState.STOPPED

        raise HerdrPayloadRejectedError(f"herdr answered the server status as `{value}`, which is not a known state")
