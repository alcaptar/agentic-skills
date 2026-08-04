from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.judge_prompt import JudgePrompt
    from slice_runner.domain.verdict import Verdict


class Verifier(ABC):
    @abstractmethod
    def verify(self, prompt: JudgePrompt) -> Verdict: ...
