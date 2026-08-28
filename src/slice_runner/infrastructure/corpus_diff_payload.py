from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.exceptions import UnreadableCorpusError
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.infrastructure.diff_stats_payload import DiffStatsPayload
from slice_runner.infrastructure.durable_ledger import ReadableLedgerRow
from slice_runner.infrastructure.json_schema import JsonSchema
from slice_runner.infrastructure.stamped_row import StampedRow

if TYPE_CHECKING:
    from slice_runner.domain.corpus_entry import CorpusEntry


class CorpusDiffPayload(StampedRow, ReadableLedgerRow):
    UNREADABLE: ClassVar[type[ValueError]] = UnreadableCorpusError

    verify_round: int
    session: str
    diff: str
    stats: DiffStatsPayload

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
            diff=entry.diff.text,
            stats=DiffStatsPayload.from_domain(entry.diff.stats),
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the corpus diff log line is not one this program wrote in this generation", cls.UNREADABLE
        )
