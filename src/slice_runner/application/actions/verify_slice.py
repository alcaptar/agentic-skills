from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from slice_runner.domain.slice_under_review import SliceUnderReview

if TYPE_CHECKING:
    from slice_runner.domain.diff_reader import DiffReader
    from slice_runner.domain.judge import Judge
    from slice_runner.domain.skill_library import SkillLibrary
    from slice_runner.domain.verification import Verification
    from slice_runner.domain.verifier import Verifier


@dataclass(frozen=True, kw_only=True, slots=True)
class VerifySliceParams:
    repo: str
    base: str


class VerifySlice:
    def __init__(self, *, reader: DiffReader, verifier: Verifier, judge: Judge, skills: SkillLibrary) -> None:
        self._reader = reader
        self._verifier = verifier
        self._judge = judge
        self._skills = skills

    def execute(self, params: VerifySliceParams) -> Verification:
        diff = self._reader.read(repo=params.repo, base=params.base)

        return self._verifier.verify(
            self._judge_reading(params.repo),
            SliceUnderReview(repo=params.repo, diff=diff),
        )

    def _judge_reading(self, repo: str) -> Judge:
        return self._judge.also_reading(Path(repo), *self._skills.directories())
