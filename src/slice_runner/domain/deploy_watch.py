from __future__ import annotations

from abc import ABC, abstractmethod


class DeployWatch(ABC):
    @abstractmethod
    def watch(self, *, worktree: str, repo: str, signal: str) -> None: ...
