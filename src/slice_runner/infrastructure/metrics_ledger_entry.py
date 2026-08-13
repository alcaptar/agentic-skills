from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Self

from pydantic import AliasChoices, Field, field_validator

from slice_runner.domain.closed_slice_record import ClosedSliceRecord
from slice_runner.domain.diff_stats import DiffStats
from slice_runner.domain.exceptions import UnreadableMetricsLogError
from slice_runner.domain.recorded_spend import RecordedSpend
from slice_runner.domain.severity_count import SeverityCount
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.corpus_verdict_payload import SeverityCountPayload
from slice_runner.infrastructure.metrics_entry_payload import (
    DiffStatsPayload,
    DurableCi,
    DurableCiIndeterminateCause,
    DurableClosure,
    DurableDiscardCause,
    DurableVerdict,
    HarnessMeasurementPayload,
)

if TYPE_CHECKING:
    from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
    from slice_runner.domain.discard_cause import DiscardCause

_IGNORED_LEGACY_KEYS = ("duracion_s", "coste_tokens")


class MetricsLedgerRowPayload(ContractModel):
    LEGACY_VERDICT: ClassVar[str] = "bloqueada-puertas"

    ts: str | None = None
    repo: str | None = None
    issue: int | None = None
    slice_id: str | None = None
    name: str | None = None
    verdict: DurableVerdict | None = Field(alias="veredicto", default=None)
    ci: DurableCi | None = None
    findings: SeverityCountPayload | None = Field(validation_alias=AliasChoices("findings", "hallazgos"), default=None)
    findings_of_the_last_round: SeverityCountPayload | None = Field(
        validation_alias=AliasChoices("findings_of_the_last_round", "hallazgos_ronda_final"), default=None
    )
    implement_retries: int = Field(alias="reintentos_implement", default=0)
    control_retries: int = Field(validation_alias=AliasChoices("reintentos_controles", "reintentos_puertas"), default=0)
    ci_retries: int = Field(alias="reintentos_ci", default=0)
    verify_retries: int = Field(alias="reintentos_verify", default=0)
    correction_retries: int = Field(
        validation_alias=AliasChoices("correction_retries", "reintentos_correcciones"), default=0
    )
    verify_discards: int = Field(alias="descartes_verify", default=0)
    discard_cause: DurableDiscardCause | None = Field(alias="descartes_verify_causa", default=None)
    ci_indeterminate_cause: DurableCiIndeterminateCause | None = Field(alias="ci_indeterminada_causa", default=None)
    harness: HarnessMeasurementPayload | None = None
    variant: str | None = Field(alias="variante", default=None)
    models: list[str] | None = Field(alias="modelos", default=None)
    debt: int = Field(validation_alias=AliasChoices("debt", "deuda"), default=0)
    diff: DiffStatsPayload | None = None
    budgets: dict[str, object] = Field(validation_alias=AliasChoices("budgets", "presupuestos"), default_factory=dict)
    models_by_role: dict[str, object] = Field(
        validation_alias=AliasChoices("models_by_role", "modelos_por_papel"), default_factory=dict
    )

    @field_validator("verdict", mode="before")
    @classmethod
    def _legacy_verdict(cls, value: object) -> object:
        return DurableVerdict.BLOCKED_CONTROLS if value == cls.LEGACY_VERDICT else value

    @classmethod
    def from_row(cls, row: dict[str, object]) -> Self:
        projected = {key: value for key, value in row.items() if key not in _IGNORED_LEGACY_KEYS}

        return cls._validated(
            projected, "the metrics log line is not one this program wrote", UnreadableMetricsLogError
        )


class MetricsLedgerEntry:
    @classmethod
    def read(cls, row: dict[str, object]) -> ClosedSliceRecord | None:
        payload = MetricsLedgerRowPayload.from_row(row)
        ts = cls._timestamp(payload.ts)
        if ts is None or payload.verdict is None or payload.ci is None:
            return None

        return ClosedSliceRecord(
            ts=ts,
            repo=payload.repo or "",
            issue=payload.issue or 0,
            slice_id=payload.slice_id or "",
            name=payload.name or "",
            state=DurableClosure.state_of(verdict=payload.verdict, ci=payload.ci),
            findings=cls._severity_count(payload.findings),
            findings_of_the_last_round=cls._severity_count(payload.findings_of_the_last_round),
            implement_retries=payload.implement_retries,
            control_retries=payload.control_retries,
            ci_retries=payload.ci_retries,
            verify_retries=payload.verify_retries,
            correction_retries=payload.correction_retries,
            verify_discards=payload.verify_discards,
            discard_cause=cls._discard_cause(payload.discard_cause),
            ci_indeterminate_cause=cls._ci_indeterminate_cause(payload.ci_indeterminate_cause),
            spend=cls._spend(payload.harness) if payload.harness is not None else None,
            variant=payload.variant,
            models=tuple(payload.models or ()),
            debt=payload.debt,
            diff=cls._diff_stats(payload.diff) if payload.diff is not None else None,
            budgets=payload.budgets,
            models_by_role=payload.models_by_role,
        )

    @staticmethod
    def _timestamp(value: str | None) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError as error:
            raise UnreadableMetricsLogError(f"the metrics log has an unreadable timestamp: {error}") from error

    @staticmethod
    def _discard_cause(cause: DurableDiscardCause | None) -> DiscardCause | None:
        return cause.to_domain() if cause is not None else None

    @staticmethod
    def _ci_indeterminate_cause(cause: DurableCiIndeterminateCause | None) -> CiIndeterminateCause | None:
        return cause.to_domain() if cause is not None else None

    @staticmethod
    def _spend(harness: HarnessMeasurementPayload) -> RecordedSpend:
        return RecordedSpend(
            cost_usd=harness.cost_usd,
            turns=harness.turns,
            duration_ms=harness.duration_ms,
            cache_read_tokens=harness.cache_read_tokens,
        )

    @staticmethod
    def _diff_stats(diff: DiffStatsPayload) -> DiffStats:
        return DiffStats(
            files_changed=diff.files_changed,
            lines_added=diff.lines_added,
            lines_deleted=diff.lines_deleted,
        )

    @staticmethod
    def _severity_count(counts: SeverityCountPayload | None) -> SeverityCount:
        if counts is None:
            return SeverityCount(high=0, medium=0, low=0)

        return SeverityCount(high=counts.high, medium=counts.medium, low=counts.low)
