from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.verification_request import VerificationRequest

if TYPE_CHECKING:
    from slice_runner.domain.diff_writer import DiffWriter
    from slice_runner.domain.verdict import Verdict
    from slice_runner.domain.verifier import Verifier


@dataclass(frozen=True, kw_only=True, slots=True)
class VerifySliceParams:
    repo: str
    base: str
    instructions: str


class VerifySlice:
    def __init__(self, *, writer: DiffWriter, verifier: Verifier) -> None:
        self._writer = writer
        self._verifier = verifier

    def execute(self, params: VerifySliceParams) -> Verdict:
        diff = self._writer.write(repo=params.repo, base=params.base)

        return self._verifier.verify(VerificationRequest(repo=params.repo, instructions=params.instructions, diff=diff))
