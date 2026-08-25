from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Self

from pydantic import AliasChoices, Field

from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.conflict_block_cause import ConflictBlockCause
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.discarded_call import DiscardedCall
from slice_runner.domain.exceptions import RunNotClosedError
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity
from slice_runner.domain.step import Step
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.corpus_verdict_payload import SeverityCountPayload
from slice_runner.infrastructure.json_schema import JsonSchema

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice import ClosedSlice
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.harness_spend import HarnessSpend


class DurableVerdict(StrEnum):
    PASS = "PASA"
    FAIL = "FALLA"
    BLOCKED_CONTROLS = "bloqueada-controles"
    BLOCKED_HYGIENE = "bloqueada-higiene"
    ABORTED_BUDGET = "abortada-presupuesto"
    ABORTED_UNMEASURED_CALL = "abortada-llamada-no-medida"


class DurableCi(StrEnum):
    GREEN = "green"
    RED = "red"
    NONE = "none"
    CONFLICT = "conflict"


class DurableDiscardCause(StrEnum):
    INCOHERENT_VERDICT = "veredicto-incoherente"
    FAILED_CALL = "llamada-fallida"

    @classmethod
    def of(cls, cause: DiscardCause) -> DurableDiscardCause:
        match cause:
            case DiscardCause.INCOHERENT_VERDICT:
                return cls.INCOHERENT_VERDICT
            case DiscardCause.FAILED_CALL:
                return cls.FAILED_CALL

    def to_domain(self) -> DiscardCause:
        match self:
            case DurableDiscardCause.INCOHERENT_VERDICT:
                return DiscardCause.INCOHERENT_VERDICT
            case DurableDiscardCause.FAILED_CALL:
                return DiscardCause.FAILED_CALL


class DurableCiIndeterminateCause(StrEnum):
    COMMAND_FAILED = "comando-fallido"
    UNREADABLE_RESPONSE = "respuesta-no-legible"

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


class DurableConflictBlockCause(StrEnum):
    TREE_STILL_CONFLICTED = "arbol-sigue-en-conflicto"
    CONTROLS_FAILED = "controles-fallaron"

    @classmethod
    def of(cls, cause: ConflictBlockCause) -> DurableConflictBlockCause:
        match cause:
            case ConflictBlockCause.TREE_STILL_CONFLICTED:
                return cls.TREE_STILL_CONFLICTED
            case ConflictBlockCause.CONTROLS_FAILED:
                return cls.CONTROLS_FAILED

    def to_domain(self) -> ConflictBlockCause:
        match self:
            case DurableConflictBlockCause.TREE_STILL_CONFLICTED:
                return ConflictBlockCause.TREE_STILL_CONFLICTED
            case DurableConflictBlockCause.CONTROLS_FAILED:
                return ConflictBlockCause.CONTROLS_FAILED


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


class HarnessMeasurementPayload(ContractModel):
    cost_usd: float = Field(alias="coste_usd")
    turns: int = Field(alias="turnos")
    duration_ms: int = Field(alias="duracion_ms")
    cache_read_tokens: int = Field(alias="tokens_cache")

    @classmethod
    def from_domain(cls, spend: HarnessSpend) -> Self:
        return cls.model_validate(
            {
                "coste_usd": spend.cost_usd,
                "turnos": spend.turns,
                "duracion_ms": spend.duration_ms,
                "tokens_cache": spend.cache_read_tokens,
            }
        )


class DiscardedCallPayload(ContractModel):
    step: Step = Field(alias="paso")
    cause: DurableDiscardCause = Field(alias="causa")
    reason: str = Field(alias="motivo")

    @classmethod
    def from_domain(cls, discarded: DiscardedCall) -> Self:
        return cls.model_validate(
            {"paso": discarded.step, "causa": DurableDiscardCause.of(discarded.cause), "motivo": discarded.reason}
        )

    def to_domain(self) -> DiscardedCall:
        return DiscardedCall(step=self.step, cause=self.cause.to_domain(), reason=self.reason)


class DiffStatsPayload(ContractModel):
    files_changed: int = Field(validation_alias=AliasChoices("files_changed", "ficheros"))
    lines_added: int = Field(validation_alias=AliasChoices("lines_added", "lineas_anadidas"))
    lines_deleted: int = Field(validation_alias=AliasChoices("lines_deleted", "lineas_borradas"))

    @classmethod
    def from_domain(cls, stats: DiffStats) -> Self:
        return cls.model_validate(
            {
                "files_changed": stats.files_changed,
                "lines_added": stats.lines_added,
                "lines_deleted": stats.lines_deleted,
            }
        )


class MetricsEntryPayload(ContractModel):
    VARIANT: ClassVar[str] = "programa"

    ts: str
    repo: str
    issue: int
    slice_id: str
    name: str
    verdict: DurableVerdict = Field(alias="veredicto")
    ci: DurableCi
    findings: SeverityCountPayload
    findings_of_the_last_round: SeverityCountPayload
    implement_retries: int = Field(alias="reintentos_implement")
    control_retries: int = Field(alias="reintentos_controles")
    ci_retries: int = Field(alias="reintentos_ci")
    verify_retries: int = Field(alias="reintentos_verify")
    correction_retries: int
    verify_discards: int = Field(alias="descartes_verify")
    understand_discards: int
    implement_discards: int
    harness: HarnessMeasurementPayload | None = None
    discarded_call: DiscardedCallPayload | None = Field(alias="descartes", default=None)
    ci_indeterminate_cause: DurableCiIndeterminateCause | None = Field(alias="ci_indeterminada_causa", default=None)
    conflict_block_cause: DurableConflictBlockCause | None = Field(alias="conflicto_causa", default=None)
    models: list[str] | None = Field(alias="modelos", default=None)
    variant: str = Field(alias="variante")
    debt: int
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
        return cls.model_validate(
            {
                "ts": ts,
                "repo": closed.repo,
                "issue": closed.issue,
                "slice_id": closed.slice_id,
                "name": closed.name,
                "veredicto": closure.verdict,
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
                "reintentos_implement": closed.run.implement_retries,
                "reintentos_controles": closed.run.control_retries,
                "reintentos_ci": closed.run.ci_retries,
                "reintentos_verify": closed.run.verify_retries,
                "correction_retries": closed.run.correction_retries,
                "descartes_verify": closed.run.verify_discards,
                "understand_discards": closed.run.understand_discards,
                "implement_discards": closed.run.implement_discards,
                "harness": HarnessMeasurementPayload.from_domain(spend) if spend.measured else None,
                "descartes": DiscardedCallPayload.from_domain(closed.discarded_call)
                if closed.discarded_call is not None
                else None,
                "ci_indeterminada_causa": DurableCiIndeterminateCause.of(closed.ci_indeterminate_cause)
                if closed.ci_indeterminate_cause
                else None,
                "conflicto_causa": DurableConflictBlockCause.of(closed.conflict_block_cause)
                if closed.conflict_block_cause
                else None,
                "modelos": list(spend.models) or None,
                "variante": cls.VARIANT,
                "debt": len(closed.debt),
                "diff": DiffStatsPayload.from_domain(closed.diff_stats) if closed.diff_stats is not None else None,
                "budgets": asdict(closed.budgets),
                "models_by_role": asdict(closed.models),
            }
        )

    def to_contract(self) -> dict[str, object]:
        return {**super().to_contract(), "duracion_s": None, "coste_tokens": None}
