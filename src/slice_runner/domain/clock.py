from __future__ import annotations

from abc import ABC, abstractmethod


class Clock(ABC):
    @abstractmethod
    def sleep(self, *, seconds: int) -> None: ...
