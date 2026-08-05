from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from slice_runner.domain.corpus_entry import CorpusEntry
from slice_runner.domain.slice_under_review import SliceUnderReview

if TYPE_CHECKING:
    from slice_runner.domain.corpus import Corpus
    from slice_runner.domain.diff_reader import DiffReader
    from slice_runner.domain.judge import Judge
    from slice_runner.domain.skill_library import SkillLibrary
    from slice_runner.domain.verification import Verification
    from slice_runner.domain.verifier import Verifier


@dataclass(frozen=True, kw_only=True, slots=True)
class VerifySliceParams:
    repo: str
    base: str
    slice_id: str


class VerifySlice:
    def __init__(
        self, *, reader: DiffReader, verifier: Verifier, judge: Judge, skills: SkillLibrary, corpus: Corpus
    ) -> None:
        self._reader = reader
        self._verifier = verifier
        self._judge = judge
        self._skills = skills
        self._corpus = corpus

    def execute(self, params: VerifySliceParams) -> Verification:
        diff = self._reader.read(repo=params.repo, base=params.base)
        verification = self._verifier.verify(
            self._judge_reading(params.repo),
            SliceUnderReview(repo=params.repo, diff=diff),
        )
        self._corpus.record(CorpusEntry(slice_id=params.slice_id, diff=diff, verdict=verification.verdict))

        return verification

    def _judge_reading(self, repo: str) -> Judge:
        return self._judge.also_reading(Path(repo), *self._skills.directories())
