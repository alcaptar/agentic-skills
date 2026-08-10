from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.step import Step


class ToolUseRecorder(ABC):
    @abstractmethod
    def record_after(self, *, slice_id: str, step: Step, session: str, repo: str) -> None: ...
