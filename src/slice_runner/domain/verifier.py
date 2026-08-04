from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.verdict import Verdict
    from slice_runner.domain.verification_request import VerificationRequest


class Verifier(ABC):
    @abstractmethod
    def verify(self, request: VerificationRequest) -> Verdict: ...
