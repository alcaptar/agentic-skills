from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.branch_catch_up_outcome import BranchCatchUpOutcome


@dataclass(frozen=True, kw_only=True, slots=True)
class BranchCatchUp:
    outcome: BranchCatchUpOutcome
    conflicted_paths: tuple[str, ...] = field(default=())
