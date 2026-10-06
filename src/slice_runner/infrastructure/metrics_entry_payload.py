from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Self

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.discarded_call import DiscardedCall
from slice_runner.domain.exceptions import RunNotClosedError, UnreadableMetricsLogError
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.step import Step
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.corpus_verdict_payload import SeverityCountPayload
from slice_runner.infrastructure.diff_stats_payload import DiffStatsPayload
from slice_runner.infrastructure.durable_ledger import ReadableLedgerRow
from slice_runner.infrastructure.json_schema import JsonSchema
from slice_runner.infrastructure.spend_payload import SpendPayload
from slice_runner.infrastructure.stamped_row import StampedRow

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice import ClosedSlice


class DurableVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED_CONTROLS = "blocked-controls"
    BLOCKED_HYGIENE = "blocked-hygiene"
    ABORTED_BUDGET = "aborted-budget"
    ABORTED_UNMEASURED_CALL = "aborted-unmeasured-call"


class DurableCi(StrEnum):
    GREEN = "green"
    RED = "red"
    NONE = "none"
    CONFLICT = "conflict"


class DurableDiscardCause(StrEnum):
    INCOHERENT_VERDICT = "incoherent-verdict"
    FAILED_CALL = "failed-call"
    NO_STRUCTURED_OUTPUT = "no-structured-output"

    @classmethod
    def of(cls, cause: DiscardCause) -> DurableDiscardCause:
        match cause:
            case DiscardCause.INCOHERENT_VERDICT:
                return cls.INCOHERENT_VERDICT
            case DiscardCause.FAILED_CALL:
                return cls.FAILED_CALL
            case DiscardCause.NO_STRUCTURED_OUTPUT:
                return cls.NO_STRUCTURED_OUTPUT

    def to_domain(self) -> DiscardCause:
        match self:
            case DurableDiscardCause.INCOHERENT_VERDICT:
                return DiscardCause.INCOHERENT_VERDICT
            case DurableDiscardCause.FAILED_CALL:
                return DiscardCause.FAILED_CALL
            case DurableDiscardCause.NO_STRUCTURED_OUTPUT:
                return DiscardCause.NO_STRUCTURED_OUTPUT


class DurableCiIndeterminateCause(StrEnum):
    COMMAND_FAILED = "command-failed"
    UNREADABLE_RESPONSE = "unreadable-response"

    @classmethod
    def of(cls, cause: CiIndeterminateCause) -> DurableCiIndeterminateCause:
        match cause:
            case CiIndeterminateCause.COMMAND_FAILED:
                return cls.COMMAND_FAILED
            case CiIndeterminateCause.UNREADABLE_RESPONSE:
                return cls.UNREADABLE_RESPONSE

    def to_domain(self) -> CiIndeterminateCause:
        match self:
            case DurableCiIndeterminateCause.COMMAND_FAILED:
                return CiIndeterminateCause.COMMAND_FAILED
            case DurableCiIndeterminateCause.UNREADABLE_RESPONSE:
                return CiIndeterminateCause.UNREADABLE_RESPONSE


@dataclass(frozen=True, kw_only=True, slots=True)
class DurableClosure:
    verdict: DurableVerdict
    ci: DurableCi

    _VERDICTS_WITH_NO_CI: ClassVar[dict[RunState, DurableVerdict]] = {
        RunState.BLOCKED_VERIFY: DurableVerdict.FAIL,
        RunState.BLOCKED_CONTROLS: DurableVerdict.BLOCKED_CONTROLS,
        RunState.BLOCKED_HYGIENE: DurableVerdict.BLOCKED_HYGIENE,
        RunState.ABORTED_BUDGET: DurableVerdict.ABORTED_BUDGET,
        RunState.ABORTED_UNMEASURED_CALL: DurableVerdict.ABORTED_UNMEASURED_CALL,
    }

    _STATES_WITH_NO_CI: ClassVar[dict[DurableVerdict, RunState]] = {
        DurableVerdict.FAIL: RunState.BLOCKED_VERIFY,
        DurableVerdict.BLOCKED_CONTROLS: RunState.BLOCKED_CONTROLS,
        DurableVerdict.BLOCKED_HYGIENE: RunState.BLOCKED_HYGIENE,
        DurableVerdict.ABORTED_BUDGET: RunState.ABORTED_BUDGET,
        DurableVerdict.ABORTED_UNMEASURED_CALL: RunState.ABORTED_UNMEASURED_CALL,
    }
    _MERGED_STATES: ClassVar[dict[DurableCi, RunState]] = {
        DurableCi.GREEN: RunState.MERGED,
        DurableCi.RED: RunState.BLOCKED_CI_RED,
        DurableCi.NONE: RunState.BLOCKED_CI_INDETERMINATE,
        DurableCi.CONFLICT: RunState.BLOCKED_CI_CONFLICT,
    }

    @classmethod
    def of(cls, state: RunState) -> DurableClosure:
        match state:
            case RunState.MERGED:
                return cls(verdict=DurableVerdict.PASS, ci=DurableCi.GREEN)
            case RunState.BLOCKED_CI_RED:
                return cls(verdict=DurableVerdict.PASS, ci=DurableCi.RED)
            case RunState.BLOCKED_CI_INDETERMINATE:
                return cls(verdict=DurableVerdict.PASS, ci=DurableCi.NONE)
            case RunState.BLOCKED_CI_CONFLICT:
                return cls(verdict=DurableVerdict.PASS, ci=DurableCi.CONFLICT)
            case (
                RunState.BLOCKED_VERIFY
                | RunState.BLOCKED_CONTROLS
                | RunState.BLOCKED_HYGIENE
                | RunState.ABORTED_BUDGET
                | RunState.ABORTED_UNMEASURED_CALL
            ):
                return cls(verdict=cls._VERDICTS_WITH_NO_CI[state], ci=DurableCi.NONE)
            case RunState.OPEN:
                raise RunNotClosedError(
                    f"a run in state {RunState.OPEN} has no verdict to record: "
                    f"the durable log is one line per closed slice"
                )

    @classmethod
    def state_of(cls, *, verdict: DurableVerdict, ci: DurableCi) -> RunState:
        match verdict:
            case DurableVerdict.PASS:
                return cls._MERGED_STATES[ci]
            case (
                DurableVerdict.FAIL
                | DurableVerdict.BLOCKED_CONTROLS
                | DurableVerdict.BLOCKED_HYGIENE
                | DurableVerdict.ABORTED_BUDGET
                | DurableVerdict.ABORTED_UNMEASURED_CALL
            ):
                return cls._STATES_WITH_NO_CI[verdict]


class DiscardedCallPayload(ContractModel):
    step: Step
    cause: DurableDiscardCause
    reason: str

    @classmethod
    def from_domain(cls, discarded: DiscardedCall) -> Self:
        return cls.model_validate(
            {"step": discarded.step, "cause": DurableDiscardCause.of(discarded.cause), "reason": discarded.reason}
        )

    def to_domain(self) -> DiscardedCall:
        return DiscardedCall(step=self.step, cause=self.cause.to_domain(), reason=self.reason)


class MetricsEntryPayload(StampedRow, ReadableLedgerRow):
    VARIANT: ClassVar[str] = "program"
    UNREADABLE: ClassVar[type[ValueError]] = UnreadableMetricsLogError

    name: str
    verdict: DurableVerdict
    ci: DurableCi
    findings: SeverityCountPayload
    findings_of_the_last_round: SeverityCountPayload
    implement_retries: int
    control_retries: int
    ci_retries: int
    verify_retries: int
    verify_discards: int
    understand_discards: int
    implement_discards: int
    harness: SpendPayload | None = None
    discarded_call: DiscardedCallPayload | None = None
    ci_indeterminate_cause: DurableCiIndeterminateCause | None = None
    variant: str
    declared_debt: int | None = None
    diff: DiffStatsPayload | None = None
    budgets: dict[str, object]
    models_by_role: dict[str, object]

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_domain(cls, closed: ClosedSlice, *, ts: str) -> Self:
        closure = DurableClosure.of(closed.state)
        spend = closed.spend
        coordinates = SliceCoordinates(
            repo=closed.repo, issue=closed.issue, slice_id=CanonicalSliceId.of_text(closed.slice_id)
        )
        return cls._stamped(
            coordinates,
            ts=ts,
            **{
                "name": closed.name,
                "verdict": closure.verdict,
                "ci": closure.ci,
                "findings": SeverityCountPayload.model_validate(
                    {
                        "high": closed.count_findings(Severity.HIGH),
                        "medium": closed.count_findings(Severity.MEDIUM),
                        "low": closed.count_findings(Severity.LOW),
                    }
                ),
                "findings_of_the_last_round": SeverityCountPayload.model_validate(
                    {
                        "high": closed.count_findings_of_the_last_round(Severity.HIGH),
                        "medium": closed.count_findings_of_the_last_round(Severity.MEDIUM),
                        "low": closed.count_findings_of_the_last_round(Severity.LOW),
                    }
                ),
                "implement_retries": closed.run.implement_retries,
                "control_retries": closed.run.control_retries,
                "ci_retries": closed.run.ci_retries,
                "verify_retries": closed.run.verify_retries,
                "verify_discards": closed.run.verify_discards,
                "understand_discards": closed.run.understand_discards,
                "implement_discards": closed.run.implement_discards,
                "harness": SpendPayload.from_domain(spend) if spend.measured else None,
                "discarded_call": DiscardedCallPayload.from_domain(closed.discarded_call)
                if closed.discarded_call is not None
                else None,
                "ci_indeterminate_cause": DurableCiIndeterminateCause.of(closed.ci_indeterminate_cause)
                if closed.ci_indeterminate_cause
                else None,
                "variant": cls.VARIANT,
                "declared_debt": len(closed.debt.left_out) if closed.debt.declared else None,
                "diff": DiffStatsPayload.from_domain(closed.diff_stats) if closed.diff_stats is not None else None,
                "budgets": asdict(closed.budgets),
                "models_by_role": asdict(closed.models),
            },
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the metrics log line is not one this program wrote in this generation", cls.UNREADABLE
        )
