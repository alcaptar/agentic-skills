from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.control_status import ControlStatus
from slice_runner.domain.outcome import Outcome

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.control_outcome import ControlOutcome
    from slice_runner.domain.control_runner import ControlRunner
    from slice_runner.domain.controls import Controls
    from slice_runner.domain.slice_identity import SliceIdentity


@dataclass(frozen=True, kw_only=True, slots=True)
class RunControlsParams:
    worktree: str
    controls: Controls
    logs: Path
    slice_id: SliceIdentity
    control_rounds_logged: int


@dataclass(frozen=True, kw_only=True, slots=True)
class RunControlsResult:
    outcome: Outcome
    red_logs: tuple[Path, ...]


class RunControls:
    def __init__(self, *, controls: ControlRunner) -> None:
        self._controls = controls

    def execute(self, params: RunControlsParams) -> RunControlsResult:
        out = params.logs / params.slice_id.canonical / f"round-{params.control_rounds_logged + 1}"
        outcomes: tuple[ControlOutcome, ...] = ()
        if params.controls.exemption_reason is None:
            outcomes = tuple(
                self._controls.run(command, repo=params.worktree, out=out) for command in params.controls.commands
            )
        red = tuple(
            outcome.log for outcome in outcomes if outcome.status is ControlStatus.RED and outcome.log is not None
        )

        return RunControlsResult(outcome=Outcome.of_the_controls(outcomes), red_logs=red)
