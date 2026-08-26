from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from slice_runner.domain.branch_catch_up_outcome import BranchCatchUpOutcome
from slice_runner.domain.exceptions import MeasuredCallError
from slice_runner.domain.merge_conflict import MergeConflict
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.staged_hygiene import StagedHygiene

if TYPE_CHECKING:
    from slice_runner.domain.branches import Branches
    from slice_runner.domain.conflict_resolver import ConflictResolver
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.source import Source
    from slice_runner.domain.workspace import Workspace


@dataclass(frozen=True, kw_only=True, slots=True)
class CatchUpBranchParams:
    repo: str
    issue: int
    slice_id: str
    worktree: str
    branch: str
    base: str
    sources: tuple[Source, ...] = field(default=())


@dataclass(frozen=True, kw_only=True, slots=True)
class CatchUpBranchResult:
    outcome: Outcome
    spend: HarnessSpend | None = None


class CatchUpBranch:
    def __init__(self, *, branches: Branches, workspace: Workspace, resolver: ConflictResolver) -> None:
        self._branches = branches
        self._workspace = workspace
        self._resolver = resolver

    def execute(self, params: CatchUpBranchParams) -> CatchUpBranchResult:
        caught_up = self._branches.catch_up(worktree=params.worktree, name=params.branch, base=params.base)
        if caught_up.outcome is BranchCatchUpOutcome.CAUGHT_UP:
            return CatchUpBranchResult(outcome=Outcome.DONE)

        return self._resolving(params, caught_up.conflicting_paths, caught_up.dirty_before_merge)

    def _resolving(
        self, params: CatchUpBranchParams, conflicting_paths: tuple[str, ...], dirty_before_merge: tuple[str, ...]
    ) -> CatchUpBranchResult:
        auto_merged_by_git = self._auto_merged_by_git(params, dirty_before_merge)
        conflict = MergeConflict(
            repo=params.repo,
            issue=params.issue,
            slice_id=params.slice_id,
            worktree=params.worktree,
            branch=params.branch,
            base=params.base,
            conflicting_paths=conflicting_paths,
            sources=params.sources,
        )
        try:
            resolution = self._resolver.resolve(conflict)
        except MeasuredCallError as rejection:
            self._branches.abort_merge(worktree=params.worktree)
            return CatchUpBranchResult(outcome=Outcome.DISCARDED, spend=rejection.spend)

        after = self._branches.changed_paths(worktree=params.worktree)
        offences = StagedHygiene.of(staged=after, declared=(*auto_merged_by_git, *conflicting_paths))
        if offences:
            self._branches.abort_merge(worktree=params.worktree)
            return CatchUpBranchResult(outcome=Outcome.HYGIENE_REJECTED, spend=resolution.spend)

        self._workspace.stage(worktree=params.worktree, paths=conflicting_paths)
        self._branches.conclude_merge(worktree=params.worktree)

        return CatchUpBranchResult(outcome=Outcome.DONE, spend=resolution.spend)

    def _auto_merged_by_git(self, params: CatchUpBranchParams, dirty_before_merge: tuple[str, ...]) -> tuple[str, ...]:
        merged_so_far = self._branches.changed_paths(worktree=params.worktree)

        return tuple(path for path in merged_so_far if path not in dirty_before_merge)
