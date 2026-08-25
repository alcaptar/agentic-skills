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

    @abstractmethod
    def conclude_merge(self, *, worktree: str) -> None: ...

    @abstractmethod
    def abort_merge(self, *, worktree: str) -> None: ...

    @abstractmethod
    def paths_touched_since_the_merge_attempt(self, *, worktree: str) -> tuple[str, ...]: ...

    @abstractmethod
    def has_leftover_conflict_markers(self, *, worktree: str, paths: tuple[str, ...]) -> bool: ...
