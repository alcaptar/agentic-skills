from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from slice_runner.domain.branch_catch_up_outcome import BranchCatchUpOutcome
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
    resolved_a_conflict: bool = False


class CatchUpBranch:
    def __init__(self, *, branches: Branches, workspace: Workspace, resolver: ConflictResolver) -> None:
        self._branches = branches
        self._workspace = workspace
        self._resolver = resolver

    def execute(self, params: CatchUpBranchParams) -> CatchUpBranchResult:
        caught_up = self._branches.catch_up(worktree=params.worktree, name=params.branch, base=params.base)
        if caught_up.outcome is BranchCatchUpOutcome.CAUGHT_UP:
            return CatchUpBranchResult(outcome=Outcome.DONE)

        resolution = self._resolver.resolve(
            MergeConflict(
                repo=params.repo,
                issue=params.issue,
                slice_id=params.slice_id,
                worktree=params.worktree,
                branch=params.branch,
                base=params.base,
                conflicted_paths=caught_up.conflicted_paths,
                sources=params.sources,
            )
        )

        touched = self._branches.paths_touched_since_the_merge_attempt(worktree=params.worktree)
        offences = StagedHygiene.of(staged=touched, declared=caught_up.conflicted_paths)
        if offences:
            self._branches.abort_merge(worktree=params.worktree)
            return CatchUpBranchResult(outcome=Outcome.HYGIENE_REJECTED, spend=resolution.spend)

        if self._branches.has_leftover_conflict_markers(worktree=params.worktree, paths=caught_up.conflicted_paths):
            self._branches.abort_merge(worktree=params.worktree)
            return CatchUpBranchResult(outcome=Outcome.FAILED, spend=resolution.spend)

        self._workspace.stage(worktree=params.worktree, paths=caught_up.conflicted_paths)
        self._branches.conclude_merge(worktree=params.worktree)

        return CatchUpBranchResult(outcome=Outcome.DONE, spend=resolution.spend, resolved_a_conflict=True)
