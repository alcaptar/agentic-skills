from __future__ import annotations

import asyncio
import time

from slice_panel.domain.clock import Clock


class AsyncioClock(Clock):
    def now(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
