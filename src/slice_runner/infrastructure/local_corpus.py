from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.corpus import Corpus
from slice_runner.infrastructure.corpus_diff_payload import CorpusDiffPayload
from slice_runner.infrastructure.corpus_verdict_payload import CorpusVerdictPayload
from slice_runner.infrastructure.durable_ledger import DurableLedger, ReadableDurableLedger

if TYPE_CHECKING:
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.corpus_entry import CorpusEntry
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.slice_coordinates import SliceCoordinates


class LocalCorpus(Corpus):
    LEDGER: ClassVar[str] = "verdicts"
    DIFF_LEDGER: ClassVar[str] = "diffs"

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock
        self._verdicts: ReadableDurableLedger[CorpusVerdictPayload] = ReadableDurableLedger(
            name=self.LEDGER, row=CorpusVerdictPayload
        )
        self._diffs: DurableLedger[CorpusDiffPayload] = DurableLedger(name=self.DIFF_LEDGER, row=CorpusDiffPayload)

    def record(self, entry: CorpusEntry) -> None:
        ts = self._clock.now().isoformat()
        self._verdicts.append(CorpusVerdictPayload.from_domain(entry, ts=ts))
        self._diffs.append(CorpusDiffPayload.from_domain(entry, ts=ts))

    def size_of_the_last_verification(self, coordinates: SliceCoordinates) -> DiffStats | None:
        latest = self._verdicts.last_row_where(lambda data: CorpusVerdictPayload.may_belong_to(data, coordinates))

        return latest.diff_stats.to_domain() if latest is not None else None
