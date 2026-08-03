from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.diff import SliceDiff
    from slice_runner.domain.verdict import Verdict


@dataclass(frozen=True, kw_only=True, slots=True)
class VerificationRequest:
    repo: str
    instructions: str
    diff: SliceDiff


class Verifier(ABC):
    @abstractmethod
    def verify(self, request: VerificationRequest) -> Verdict: ...
