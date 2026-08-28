from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.closed_slice import ClosedSlice
from slice_runner.domain.run_state import RunState
from slice_runner.domain.slice_coordinates import SliceCoordinates

if TYPE_CHECKING:
    from slice_runner.domain.budgets import Budgets
    from slice_runner.domain.call_spend_log import CallSpendLog
    from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
    from slice_runner.domain.corpus import Corpus
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.discarded_call import DiscardedCall
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.metrics_log import MetricsLog
    from slice_runner.domain.role_models import RoleModels
    from slice_runner.domain.run import Run
    from slice_runner.domain.run_repository import RunRepository


@dataclass(frozen=True, kw_only=True, slots=True)
class RecordClosureParams:
    repo: str
    issue: int
    slice_id: str
    name: str
    state: RunState
    run: Run
    budgets: Budgets
    models: RoleModels
    findings: tuple[Finding, ...] = field(default=())
    findings_of_the_last_round: tuple[Finding, ...] = field(default=())
    discarded_call: DiscardedCall | None = None
    ci_indeterminate_cause: CiIndeterminateCause | None = None
    debt: tuple[str, ...] = field(default=())
    conflicting_paths: tuple[str, ...] = field(default=())


class RecordClosure:
    def __init__(
        self, *, metrics: MetricsLog, repository: RunRepository, spend_log: CallSpendLog, corpus: Corpus
    ) -> None:
        self._metrics = metrics
        self._repository = repository
        self._spend_log = spend_log
        self._corpus = corpus

    def execute(self, params: RecordClosureParams) -> None:
        spend = self._spend_of(params)
        self._metrics.record(
            ClosedSlice(
                repo=params.repo,
                issue=params.issue,
                slice_id=params.slice_id,
                name=params.name,
                state=params.state,
                run=params.run,
                budgets=params.budgets,
                models=params.models,
                spends=(spend,) if spend.measured else (),
                findings=params.findings,
                findings_of_the_last_round=params.findings_of_the_last_round,
                discarded_call=params.discarded_call,
                ci_indeterminate_cause=params.ci_indeterminate_cause,
                debt=params.debt,
                diff_stats=self._size_of(params),
            )
        )
        if params.state is RunState.BLOCKED_VERIFY and params.findings_of_the_last_round:
            self._repository.publish_findings(
                repo=params.repo, issue=params.issue, findings=params.findings_of_the_last_round
            )
        if params.state is RunState.BLOCKED_CI_CONFLICT and params.conflicting_paths:
            self._repository.publish_catch_up_conflict(
                repo=params.repo, issue=params.issue, paths=params.conflicting_paths
            )

    def _spend_of(self, params: RecordClosureParams) -> HarnessSpend:
        return self._spend_log.spend_of_the_slice(self._coordinates_of(params))

    def _size_of(self, params: RecordClosureParams) -> DiffStats | None:
        return self._corpus.size_of_the_last_verification(self._coordinates_of(params))

    @staticmethod
    def _coordinates_of(params: RecordClosureParams) -> SliceCoordinates:
        return SliceCoordinates(
            repo=params.repo, issue=params.issue, slice_id=CanonicalSliceId.of_text(params.slice_id)
        )
