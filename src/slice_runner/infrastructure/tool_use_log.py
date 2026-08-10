from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.step import Step


@dataclass(frozen=True, kw_only=True, slots=True)
class ToolUse:
    turn: int
    tool: str
    path: str | None


@dataclass(frozen=True, kw_only=True, slots=True)
class HarnessCallToolUse:
    slice_id: str
    step: Step
    session: str
    uses: tuple[ToolUse, ...]


class ToolUseLog(ABC):
    @abstractmethod
    def record(self, call: HarnessCallToolUse) -> None: ...
