from __future__ import annotations

from abc import ABC, abstractmethod


class Forum(ABC):
    @abstractmethod
    def open_pull_request(self, *, repo: str, branch: str) -> int | None: ...
