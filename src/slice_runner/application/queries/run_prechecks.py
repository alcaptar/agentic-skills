from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import SourcesBudgetExceededError, UnreadableSourceError, UnresolvableBaseError
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.precheck_result import PrecheckResult
from slice_runner.domain.prechecks import GroundSignals, Prechecks, SourcesCheck

if TYPE_CHECKING:
    from slice_runner.domain.branches import Branches
    from slice_runner.domain.forum import Forum
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.source import Source
    from slice_runner.domain.source_reader import SourceReader
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class RunPrechecksParams:
    repo: str
    worktree: str
    branch: str
    base: str
    subissue: SubIssue
    parent: ParentIssue


class RunPrechecks:
    def __init__(self, *, branches: Branches, forum: Forum, sources: SourceReader) -> None:
        self._branches = branches
        self._forum = forum
        self._sources = sources

    def execute(self, params: RunPrechecksParams) -> PrecheckResult:
        sources_check, reason = self._sources_check(worktree=params.worktree, sources=params.parent.sources)
        outcome = Prechecks.of(
            subissue=params.subissue,
            parent=params.parent,
            base_resolves_on_remote=self._base_resolves_on_remote(worktree=params.worktree, base=params.base),
            ground=GroundSignals(
                branch_exists=self._branches.exists(worktree=params.worktree, name=params.branch),
                open_pull_request=self._forum.open_pull_request(repo=params.repo, branch=params.branch),
                sources_check=sources_check,
            ),
        )
        if outcome in (PrecheckOutcome.UNREADABLE_SOURCE, PrecheckOutcome.SOURCES_OVER_BUDGET):
            return PrecheckResult(outcome=outcome, reason=reason)

        return PrecheckResult(outcome=outcome)

    def _base_resolves_on_remote(self, *, worktree: str, base: str) -> bool:
        try:
            self._branches.commits_behind_remote(worktree=worktree, base=base)
        except UnresolvableBaseError:
            return False

        return True

    def _sources_check(self, *, worktree: str, sources: tuple[Source, ...]) -> tuple[SourcesCheck, str | None]:
        try:
            self._sources.read_all(worktree=worktree, sources=sources)
        except UnreadableSourceError as error:
            return SourcesCheck.UNREADABLE, str(error)
        except SourcesBudgetExceededError as error:
            return SourcesCheck.OVER_BUDGET, str(error)

        return SourcesCheck.READABLE, None
