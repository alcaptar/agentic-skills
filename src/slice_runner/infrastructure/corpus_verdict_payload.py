from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import AliasChoices, Field

from slice_runner.domain.severity import Severity
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.json_schema import JsonSchema
from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.domain.corpus_entry import CorpusEntry
    from slice_runner.domain.verdict import Verdict


class SeverityCountPayload(ContractModel):
    high: int = Field(validation_alias=AliasChoices("high", "alta"))
    medium: int = Field(validation_alias=AliasChoices("medium", "media"))
    low: int = Field(validation_alias=AliasChoices("low", "baja"))

    @classmethod
    def from_domain(cls, verdict: Verdict) -> Self:
        return cls.model_validate(
            {
                "high": verdict.count_of(Severity.HIGH),
                "medium": verdict.count_of(Severity.MEDIUM),
                "low": verdict.count_of(Severity.LOW),
            }
        )


class CorpusVerdictPayload(ContractModel):
    slice_id: str
    verify_round: int
    session: str
    verdict: VerdictPayload
    severity_counts: SeverityCountPayload
    repo: str | None = None
    issue: int | None = None
    ts: str | None = None

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_domain(cls, entry: CorpusEntry, *, ts: str) -> Self:
        return cls.model_validate(
            {
                "slice_id": entry.slice_id,
                "verify_round": entry.verify_round,
                "session": entry.session,
                "verdict": VerdictPayload.from_domain(entry.verdict),
                "severity_counts": SeverityCountPayload.from_domain(entry.verdict),
                "repo": entry.repo,
                "issue": entry.issue,
                "ts": ts,
            }
        )
