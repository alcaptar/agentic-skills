from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from slice_runner.domain.corpus_entry import CorpusEntry
from slice_runner.domain.slice_under_review import SliceUnderReview

if TYPE_CHECKING:
    from slice_runner.domain.checklist_entry import ChecklistEntry
    from slice_runner.domain.corpus import Corpus
    from slice_runner.domain.diff_reader import DiffReader
    from slice_runner.domain.judge import Judge
    from slice_runner.domain.skill_library import SkillLibrary
    from slice_runner.domain.source import Source
    from slice_runner.domain.verification import Verification
    from slice_runner.domain.verifier import Verifier


@dataclass(frozen=True, kw_only=True, slots=True)
class VerifySliceParams:
    repo: str
    issue: int
    worktree: str
    base: str
    slice_id: str
    prior_art: str
    signal: str
    criteria: tuple[str, ...]
    sources: tuple[Source, ...]
    checklist: tuple[ChecklistEntry, ...]


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
        diff = self._reader.read(repo=params.worktree, base=params.base)
        verification = self._verifier.verify(
            self._judge_reading(params.worktree),
            SliceUnderReview(
                slice_id=params.slice_id,
                repo=params.repo,
                issue=params.issue,
                worktree=params.worktree,
                diff=diff,
                prior_art=params.prior_art,
                signal=params.signal,
                criteria=params.criteria,
                sources=params.sources,
                checklist=params.checklist,
            ),
        )
        self._corpus.record(
            CorpusEntry(
                repo=params.repo,
                issue=params.issue,
                slice_id=params.slice_id,
                diff=diff,
                verdict=verification.verdict,
            )
        )

        return verification

    def _judge_reading(self, worktree: str) -> Judge:
        return self._judge.also_reading(Path(worktree), *self._skills.directories())
