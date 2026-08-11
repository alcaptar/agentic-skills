from __future__ import annotations

from abc import ABC, abstractmethod


class Branches(ABC):
    @abstractmethod
    def exists(self, *, worktree: str, name: str) -> bool: ...

    @abstractmethod
    def create(self, *, worktree: str, name: str, base: str) -> None: ...

    @abstractmethod
    def commits_behind_remote(self, *, worktree: str, base: str) -> int: ...
