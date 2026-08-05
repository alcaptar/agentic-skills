from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.run_state import RunState

if TYPE_CHECKING:
    from slice_runner.domain.run import Run


@dataclass(frozen=True, kw_only=True, slots=True)
class Transition:
    run: Run
    state: RunState = RunState.OPEN
    wait_seconds: int = 0
