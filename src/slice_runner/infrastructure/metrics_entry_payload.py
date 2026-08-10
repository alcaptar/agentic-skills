from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Self

from pydantic import Field

from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.exceptions import RunNotClosedError
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.corpus_entry_payload import SeverityCountPayload

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice import ClosedSlice
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


class MetricsEntryPayload(ContractModel):
    VARIANT: ClassVar[str] = "programa"

    ts: str
    repo: str
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
    verify_discards: int = Field(alias="descartes_verify")
    harness: HarnessMeasurementPayload | None = None
    discard_cause: DurableDiscardCause | None = Field(alias="descartes_verify_causa", default=None)
    models: list[str] | None = Field(alias="modelos", default=None)
    variant: str = Field(alias="variante")

    @classmethod
    def from_domain(cls, closed: ClosedSlice, *, ts: str) -> Self:
        closure = DurableClosure.of(closed.state)
        spend = closed.spend
        return cls.model_validate(
            {
                "ts": ts,
                "repo": closed.repo,
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
                "descartes_verify": closed.run.verify_discards,
                "harness": HarnessMeasurementPayload.from_domain(spend) if spend.measured else None,
                "descartes_verify_causa": DurableDiscardCause.of(closed.discard_cause)
                if closed.discard_cause
                else None,
                "modelos": list(spend.models) or None,
                "variante": cls.VARIANT,
            }
        )

    def to_contract(self) -> dict[str, object]:
        return {**super().to_contract(), "duracion_s": None, "coste_tokens": None}
