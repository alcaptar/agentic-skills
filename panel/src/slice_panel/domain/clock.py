from __future__ import annotations

from abc import ABC, abstractmethod


class Clock(ABC):
    @abstractmethod
    def now(self) -> float: ...

    @abstractmethod
    async def sleep(self, seconds: float) -> None: ...
