from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import BranchMismatchError, ProtectedBranchError
from slice_runner.domain.protected_branch import ProtectedBranch

if TYPE_CHECKING:
    from slice_runner.domain.forum import Forum
    from slice_runner.domain.workspace import Workspace


@dataclass(frozen=True, kw_only=True, slots=True)
class DeliverSliceParams:
    worktree: str
    repo: str
    branch: str
    base: str
    title: str
    commit_message: str
    body: str


class DeliverSlice:
    def __init__(self, *, workspace: Workspace, forum: Forum) -> None:
        self._workspace = workspace
        self._forum = forum

    def execute(self, params: DeliverSliceParams) -> int:
        standing_on = self._workspace.current_branch(worktree=params.worktree)
        if ProtectedBranch.protects(standing_on):
            raise ProtectedBranchError(f"refusing to commit on {standing_on}: a slice is delivered from its own branch")
        if standing_on != params.branch:
            raise BranchMismatchError(
                f"the worktree stands on {standing_on} and the slice declared {params.branch}: "
                f"the commit and the pull request would land on different branches"
            )

        self._workspace.commit(worktree=params.worktree, message=params.commit_message)
        self._workspace.push(worktree=params.worktree, branch=params.branch)

        already_open = self._forum.open_pull_request(repo=params.repo, branch=params.branch)
        if already_open is not None:
            return already_open

        return self._forum.create_pull_request(
            repo=params.repo, branch=params.branch, base=params.base, title=params.title, body=params.body
        )
