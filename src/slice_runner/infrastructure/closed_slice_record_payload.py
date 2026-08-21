from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step
from slice_runner.infrastructure.contract_model import ContractModel

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice_record import ClosedSliceRecord
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.discarded_call import DiscardedCall
    from slice_runner.domain.recorded_spend import RecordedSpend
    from slice_runner.domain.severity_count import SeverityCount


class RecordedSpendPayload(ContractModel):
    cost_usd: float
    turns: int
    duration_ms: int
    cache_read_tokens: int

    @classmethod
    def from_domain(cls, spend: RecordedSpend) -> Self:
        return cls(
            cost_usd=spend.cost_usd,
            turns=spend.turns,
            duration_ms=spend.duration_ms,
            cache_read_tokens=spend.cache_read_tokens,
        )


class SeverityCountPayload(ContractModel):
    high: int
    medium: int
    low: int

    @classmethod
    def from_domain(cls, count: SeverityCount) -> Self:
        return cls(high=count.high, medium=count.medium, low=count.low)


class DiffStatsPayload(ContractModel):
    files_changed: int
    lines_added: int
    lines_deleted: int

    @classmethod
    def from_domain(cls, stats: DiffStats) -> Self:
        return cls(files_changed=stats.files_changed, lines_added=stats.lines_added, lines_deleted=stats.lines_deleted)


class DiscardedCallPayload(ContractModel):
    step: Step
    cause: DiscardCause
    reason: str

    @classmethod
    def from_domain(cls, discarded: DiscardedCall) -> Self:
        return cls(step=discarded.step, cause=discarded.cause, reason=discarded.reason)


class ClosedSliceRecordPayload(ContractModel):
    ts: str
    repo: str
    issue: int
    slice_id: str
    name: str
    state: RunState
    findings: SeverityCountPayload
    findings_of_the_last_round: SeverityCountPayload
    implement_retries: int
    control_retries: int
    ci_retries: int
    verify_retries: int
    correction_retries: int
    verify_discards: int
    understand_discards: int
    implement_discards: int
    discarded_call: DiscardedCallPayload | None = None
    ci_indeterminate_cause: CiIndeterminateCause | None = None
    spend: RecordedSpendPayload | None = None
    variant: str | None = None
    models: tuple[str, ...] = ()
    debt: int
    diff: DiffStatsPayload | None = None
    budgets: dict[str, object]
    models_by_role: dict[str, object]

    @classmethod
    def from_domain(cls, record: ClosedSliceRecord) -> Self:
        return cls.model_validate(
            {
                "ts": record.ts.isoformat(),
                "repo": record.repo,
                "issue": record.issue,
                "slice_id": record.slice_id,
                "name": record.name,
                "state": record.state,
                "findings": SeverityCountPayload.from_domain(record.findings),
                "findings_of_the_last_round": SeverityCountPayload.from_domain(record.findings_of_the_last_round),
                "implement_retries": record.implement_retries,
                "control_retries": record.control_retries,
                "ci_retries": record.ci_retries,
                "verify_retries": record.verify_retries,
                "correction_retries": record.correction_retries,
                "verify_discards": record.verify_discards,
                "understand_discards": record.understand_discards,
                "implement_discards": record.implement_discards,
                "discarded_call": DiscardedCallPayload.from_domain(record.discarded_call)
                if record.discarded_call is not None
                else None,
                "ci_indeterminate_cause": record.ci_indeterminate_cause,
                "spend": RecordedSpendPayload.from_domain(record.spend) if record.spend is not None else None,
                "variant": record.variant,
                "models": record.models,
                "debt": record.debt,
                "diff": DiffStatsPayload.from_domain(record.diff) if record.diff is not None else None,
                "budgets": record.budgets,
                "models_by_role": record.models_by_role,
            }
        )
