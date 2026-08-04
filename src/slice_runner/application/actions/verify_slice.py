from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.judge_prompt import JudgePrompt

if TYPE_CHECKING:
    from slice_runner.domain.diff_reader import DiffReader
    from slice_runner.domain.prompt_provider import PromptProvider
    from slice_runner.domain.slice_diff import SliceDiff
    from slice_runner.domain.verdict import Verdict
    from slice_runner.domain.verifier import Verifier


@dataclass(frozen=True, kw_only=True, slots=True)
class VerifySliceParams:
    repo: str
    base: str


class VerifySlice:
    def __init__(self, *, reader: DiffReader, verifier: Verifier, prompt_provider: PromptProvider) -> None:
        self._reader = reader
        self._verifier = verifier
        self._prompt_provider = prompt_provider

    def execute(self, params: VerifySliceParams) -> Verdict:
        diff = self._reader.read(repo=params.repo, base=params.base)

        return self._verifier.verify(self._prompt(repo=params.repo, diff=diff))

    def _prompt(self, *, repo: str, diff: SliceDiff) -> JudgePrompt:
        return JudgePrompt(
            rubric=self._prompt_provider.rubric(),
            repo=repo,
            diff=diff,
        )
