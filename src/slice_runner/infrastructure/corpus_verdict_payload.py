from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.severity import Severity
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.json_schema import JsonSchema
from slice_runner.infrastructure.stamped_row import StampedRow
from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.domain.corpus_entry import CorpusEntry
    from slice_runner.domain.verdict import Verdict


class SeverityCountPayload(ContractModel):
    high: int
    medium: int
    low: int

    @classmethod
    def from_domain(cls, verdict: Verdict) -> Self:
        return cls.model_validate(
            {
                "high": verdict.count_of(Severity.HIGH),
                "medium": verdict.count_of(Severity.MEDIUM),
                "low": verdict.count_of(Severity.LOW),
            }
        )


class CorpusVerdictPayload(StampedRow):
    verify_round: int
    session: str
    verdict: VerdictPayload
    severity_counts: SeverityCountPayload

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_domain(cls, entry: CorpusEntry, *, ts: str) -> Self:
        coordinates = SliceCoordinates(
            repo=entry.repo, issue=entry.issue, slice_id=CanonicalSliceId.of_text(entry.slice_id)
        )

        return cls._stamped(
            coordinates,
            ts=ts,
            verify_round=entry.verify_round,
            session=entry.session,
            verdict=VerdictPayload.from_domain(entry.verdict),
            severity_counts=SeverityCountPayload.from_domain(entry.verdict),
        )
