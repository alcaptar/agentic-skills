from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from slice_runner.domain.closed_slice import ClosedSlice
from slice_runner.domain.run_state import RunState

if TYPE_CHECKING:
    from slice_runner.domain.budgets import Budgets
    from slice_runner.domain.call_spend_log import CallSpendLog
    from slice_runner.domain.call_trace import CallTrace
    from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
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
    diff_stats: DiffStats | None = None


class RecordClosure:
    def __init__(
        self, *, metrics: MetricsLog, repository: RunRepository, trace: CallTrace, spend_log: CallSpendLog
    ) -> None:
        self._metrics = metrics
        self._repository = repository
        self._trace = trace
        self._spend_log = spend_log

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
                diff_stats=params.diff_stats,
            )
        )
        if params.state is RunState.BLOCKED_VERIFY and params.findings_of_the_last_round:
            self._repository.publish_findings(
                repo=params.repo, issue=params.issue, findings=params.findings_of_the_last_round
            )

    def _spend_of(self, params: RecordClosureParams) -> HarnessSpend:
        calls = self._trace.calls_of(repo=params.repo, issue=params.issue, slice_id=params.slice_id)
        sessions = tuple(call.session for call in calls)

        return self._spend_log.spend_of(sessions)
