from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.control_command import ControlCommand
    from slice_runner.domain.source import Source


@dataclass(frozen=True, kw_only=True, slots=True)
class ParentIssue:
    intention: str
    sources: tuple[Source, ...]
    controls: tuple[ControlCommand, ...]
    subissue_count: int
