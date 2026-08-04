from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.slice_diff import SliceDiff


@dataclass(frozen=True, kw_only=True, slots=True)
class JudgePrompt:
    rubric: str
    repo: str
    diff: SliceDiff
