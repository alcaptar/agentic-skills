from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Self

from pydantic import Field

from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.exceptions import RunNotClosedError
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.corpus_entry_payload import SeverityCountPayload

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


class DurableCi(StrEnum):
    GREEN = "green"
    RED = "red"
    NONE = "none"


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


@dataclass(frozen=True, kw_only=True, slots=True)
class DurableClosure:
    verdict: DurableVerdict
    ci: DurableCi

    _VERDICTS_WITH_NO_CI: ClassVar[dict[RunState, DurableVerdict]] = {
        RunState.BLOCKED_VERIFY: DurableVerdict.FAIL,
        RunState.BLOCKED_CONTROLS: DurableVerdict.BLOCKED_CONTROLS,
        RunState.BLOCKED_HYGIENE: DurableVerdict.BLOCKED_HYGIENE,
        RunState.ABORTED_BUDGET: DurableVerdict.ABORTED_BUDGET,
    }

    _STATES_WITH_NO_CI: ClassVar[dict[DurableVerdict, RunState]] = {
        DurableVerdict.FAIL: RunState.BLOCKED_VERIFY,
        DurableVerdict.BLOCKED_CONTROLS: RunState.BLOCKED_CONTROLS,
        DurableVerdict.BLOCKED_HYGIENE: RunState.BLOCKED_HYGIENE,
        DurableVerdict.ABORTED_BUDGET: RunState.ABORTED_BUDGET,
    }
    _MERGED_STATES: ClassVar[dict[DurableCi, RunState]] = {
        DurableCi.GREEN: RunState.MERGED,
        DurableCi.RED: RunState.BLOCKED_CI_RED,
        DurableCi.NONE: RunState.BLOCKED_CI_INDETERMINATE,
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
            case (
                RunState.BLOCKED_VERIFY | RunState.BLOCKED_CONTROLS | RunState.BLOCKED_HYGIENE | RunState.ABORTED_BUDGET
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


class DiffStatsPayload(ContractModel):
    files_changed: int = Field(alias="ficheros")
    lines_added: int = Field(alias="lineas_anadidas")
    lines_deleted: int = Field(alias="lineas_borradas")

    @classmethod
    def from_domain(cls, stats: DiffStats) -> Self:
        return cls.model_validate(
            {
                "ficheros": stats.files_changed,
                "lineas_anadidas": stats.lines_added,
                "lineas_borradas": stats.lines_deleted,
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
    findings: SeverityCountPayload = Field(alias="hallazgos")
    findings_of_the_last_round: SeverityCountPayload = Field(alias="hallazgos_ronda_final")
    implement_retries: int = Field(alias="reintentos_implement")
    control_retries: int = Field(alias="reintentos_controles")
    ci_retries: int = Field(alias="reintentos_ci")
    verify_retries: int = Field(alias="reintentos_verify")
    correction_retries: int = Field(alias="reintentos_correcciones")
    verify_discards: int = Field(alias="descartes_verify")
    harness: HarnessMeasurementPayload | None = None
    discard_cause: DurableDiscardCause | None = Field(alias="descartes_verify_causa", default=None)
    ci_indeterminate_cause: DurableCiIndeterminateCause | None = Field(alias="ci_indeterminada_causa", default=None)
    models: list[str] | None = Field(alias="modelos", default=None)
    variant: str = Field(alias="variante")
    debt: int = Field(alias="deuda")
    diff: DiffStatsPayload | None = None
    budgets: dict[str, object] = Field(alias="presupuestos")
    models_by_role: dict[str, object] = Field(alias="modelos_por_papel")

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
                "hallazgos": SeverityCountPayload.model_validate(
                    {str(severity): closed.count_findings(severity) for severity in Severity}
                ),
                "hallazgos_ronda_final": SeverityCountPayload.model_validate(
                    {str(severity): closed.count_findings_of_the_last_round(severity) for severity in Severity}
                ),
                "reintentos_implement": closed.run.implement_retries,
                "reintentos_controles": closed.run.control_retries,
                "reintentos_ci": closed.run.ci_retries,
                "reintentos_verify": closed.run.verify_retries,
                "reintentos_correcciones": closed.run.correction_retries,
                "descartes_verify": closed.run.verify_discards,
                "harness": HarnessMeasurementPayload.from_domain(spend) if spend.measured else None,
                "descartes_verify_causa": DurableDiscardCause.of(closed.discard_cause)
                if closed.discard_cause
                else None,
                "ci_indeterminada_causa": DurableCiIndeterminateCause.of(closed.ci_indeterminate_cause)
                if closed.ci_indeterminate_cause
                else None,
                "modelos": list(spend.models) or None,
                "variante": cls.VARIANT,
                "deuda": len(closed.debt),
                "diff": DiffStatsPayload.from_domain(closed.diff_stats) if closed.diff_stats is not None else None,
                "presupuestos": asdict(closed.budgets),
                "modelos_por_papel": asdict(closed.models),
            }
        )

    def to_contract(self) -> dict[str, object]:
        return {**super().to_contract(), "duracion_s": None, "coste_tokens": None}
