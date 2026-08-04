from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.judge_prompt import JudgePrompt

if TYPE_CHECKING:
    from slice_runner.domain.diff_on_disk import DiffOnDisk
    from slice_runner.domain.diff_writer import DiffWriter
    from slice_runner.domain.prompt_provider import PromptProvider
    from slice_runner.domain.verdict import Verdict
    from slice_runner.domain.verifier import Verifier


@dataclass(frozen=True, kw_only=True, slots=True)
class VerifySliceParams:
    repo: str
    base: str


class VerifySlice:
    def __init__(self, *, writer: DiffWriter, verifier: Verifier, prompt_provider: PromptProvider) -> None:
        self._writer = writer
        self._verifier = verifier
        self._prompt_provider = prompt_provider

    def execute(self, params: VerifySliceParams) -> Verdict:
        diff = self._writer.write(repo=params.repo, base=params.base)

        return self._verifier.verify(self._prompt(repo=params.repo, diff=diff))

    def _prompt(self, *, repo: str, diff: DiffOnDisk) -> JudgePrompt:
        return JudgePrompt(
            system_template=self._prompt_provider.system_template(),
            repo=repo,
            diff=diff,
        )
