from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.prechecks import Prechecks

if TYPE_CHECKING:
    from slice_runner.domain.branches import Branches
    from slice_runner.domain.forum import Forum
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.precheck_outcome import PrecheckOutcome
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class RunPrechecksParams:
    repo: str
    worktree: str
    branch: str
    subissue: SubIssue
    parent: ParentIssue


class RunPrechecks:
    def __init__(self, *, branches: Branches, forum: Forum) -> None:
        self._branches = branches
        self._forum = forum

    def execute(self, params: RunPrechecksParams) -> PrecheckOutcome:
        return Prechecks.of(
            subissue=params.subissue,
            parent=params.parent,
            branch_exists=self._branches.exists(worktree=params.worktree, name=params.branch),
            open_pull_request=self._forum.open_pull_request(repo=params.repo, branch=params.branch),
        )
