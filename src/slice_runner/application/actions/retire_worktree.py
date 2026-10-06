from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import WorktreeRetirementError
from slice_runner.domain.worktree_retirement import WorktreeRetirement
from slice_runner.domain.worktree_retirement_policy import WorktreeRetirementPolicy

if TYPE_CHECKING:
    from slice_runner.domain.worktrees import Worktrees


@dataclass(frozen=True, kw_only=True, slots=True)
class RetireWorktreeParams:
    root: str
    worktree: str
    branch: str


@dataclass(frozen=True, kw_only=True, slots=True)
class RetireWorktreeResult:
    retirement: WorktreeRetirement


class RetireWorktree:
    def __init__(self, *, worktrees: Worktrees) -> None:
        self._worktrees = worktrees

    def execute(self, params: RetireWorktreeParams) -> RetireWorktreeResult:
        if not self._is_mounted(params):
            return RetireWorktreeResult(retirement=WorktreeRetirement.NOT_MOUNTED)

        return RetireWorktreeResult(retirement=self._retiring(params))

    def _is_mounted(self, params: RetireWorktreeParams) -> bool:
        return any(
            entry.path == params.worktree and entry.branch == params.branch
            for entry in self._worktrees.listed(root=params.root)
        )

    def _retiring(self, params: RetireWorktreeParams) -> WorktreeRetirement:
        try:
            verdict = WorktreeRetirementPolicy.of(
                uncommitted=self._worktrees.has_uncommitted_work(path=params.worktree),
                local_only_commits=self._worktrees.local_only_commits(root=params.root, branch=params.branch),
            )
        except WorktreeRetirementError:
            return WorktreeRetirement.KEPT_UNVERIFIABLE
        if verdict is not WorktreeRetirement.RETIRED:
            return verdict

        return self._removing(params)

    def _removing(self, params: RetireWorktreeParams) -> WorktreeRetirement:
        try:
            self._worktrees.remove(root=params.root, path=params.worktree)
            self._worktrees.delete_branch(root=params.root, branch=params.branch)
        except WorktreeRetirementError:
            return WorktreeRetirement.KEPT_REMOVAL_FAILED

        return WorktreeRetirement.RETIRED
