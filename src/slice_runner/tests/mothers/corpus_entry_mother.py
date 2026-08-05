from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.corpus_entry import CorpusEntry
from slice_runner.tests.mothers.verdict_mother import VerdictMother
from slice_runner.tests.mothers.verification_mother import SliceDiffMother

if TYPE_CHECKING:
    from slice_runner.domain.verdict import Verdict


class CorpusEntryMother:
    SLICE_ID: ClassVar[str] = "slice-11"

    @classmethod
    def of_the_slice(cls, *, slice_id: str | None = None, verdict: Verdict | None = None) -> CorpusEntry:
        return CorpusEntry(
            slice_id=slice_id or cls.SLICE_ID,
            diff=SliceDiffMother.of_the_slice(),
            verdict=verdict or VerdictMother.passing(),
        )
