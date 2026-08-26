from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.branch_catch_up import BranchCatchUp


class Branches(ABC):
    @abstractmethod
    def exists(self, *, worktree: str, name: str) -> bool: ...

    @abstractmethod
    def create(self, *, worktree: str, name: str, base: str) -> None: ...

    @abstractmethod
    def commits_behind_remote(self, *, worktree: str, base: str) -> int: ...

    @abstractmethod
    def catch_up(self, *, worktree: str, name: str, base: str) -> BranchCatchUp: ...
