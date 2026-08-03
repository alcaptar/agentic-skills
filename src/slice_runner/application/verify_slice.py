from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.verification import VerificationRequest

if TYPE_CHECKING:
    from slice_runner.domain.diff import DiffBundler
    from slice_runner.domain.verdict import Verdict
    from slice_runner.domain.verification import Verifier


@dataclass(frozen=True, kw_only=True, slots=True)
class VerifySliceParams:
    repo: str
    base: str
    instructions: str


class VerifySlice:
    def __init__(self, *, bundler: DiffBundler, verifier: Verifier) -> None:
        self._bundler = bundler
        self._verifier = verifier

    def execute(self, params: VerifySliceParams) -> Verdict:
        diff = self._bundler.bundle(repo=params.repo, base=params.base)
        return self._verifier.verify(VerificationRequest(repo=params.repo, instructions=params.instructions, diff=diff))
