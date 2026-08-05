from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import Field

from slice_runner.domain.severity import Severity
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.domain.corpus_entry import CorpusEntry
    from slice_runner.domain.verdict import Verdict


class SeverityCountPayload(ContractModel):
    high: int = Field(alias="alta")
    medium: int = Field(alias="media")
    low: int = Field(alias="baja")

    @classmethod
    def from_domain(cls, verdict: Verdict) -> Self:
        return cls.model_validate({str(severity): verdict.count_of(severity) for severity in Severity})


class CorpusEntryPayload(ContractModel):
    slice_id: str
    diff: str
    verdict: VerdictPayload
    severity_counts: SeverityCountPayload

    @classmethod
    def from_domain(cls, entry: CorpusEntry) -> Self:
        return cls.model_validate(
            {
                "slice_id": entry.slice_id,
                "diff": entry.diff.text,
                "verdict": VerdictPayload.from_domain(entry.verdict),
                "severity_counts": SeverityCountPayload.from_domain(entry.verdict),
            }
        )
