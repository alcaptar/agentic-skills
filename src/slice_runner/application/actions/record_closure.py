from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from slice_runner.domain.closed_slice import ClosedSlice
from slice_runner.domain.run_state import RunState

if TYPE_CHECKING:
    from slice_runner.domain.budgets import Budgets
    from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.discard_cause import DiscardCause
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
    spends: tuple[HarnessSpend, ...] = field(default=())
    findings: tuple[Finding, ...] = field(default=())
    findings_of_the_last_round: tuple[Finding, ...] = field(default=())
    discard_cause: DiscardCause | None = None
    ci_indeterminate_cause: CiIndeterminateCause | None = None
    debt: tuple[str, ...] = field(default=())
    diff_stats: DiffStats | None = None


class RecordClosure:
    def __init__(self, *, metrics: MetricsLog, repository: RunRepository) -> None:
        self._metrics = metrics
        self._repository = repository

    def execute(self, params: RecordClosureParams) -> None:
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
                spends=tuple(spend for spend in params.spends if spend.measured),
                findings=params.findings,
                findings_of_the_last_round=params.findings_of_the_last_round,
                discard_cause=params.discard_cause,
                ci_indeterminate_cause=params.ci_indeterminate_cause,
                debt=params.debt,
                diff_stats=params.diff_stats,
            )
        )
        if params.state is RunState.BLOCKED_VERIFY and params.findings_of_the_last_round:
            self._repository.publish_findings(
                repo=params.repo, issue=params.issue, findings=params.findings_of_the_last_round
            )
