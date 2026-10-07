from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from slice_panel.domain.mounting_step import MountingStep
    from slice_panel.domain.process_outcome import ProcessOutcome


class ProcessTimedOutError(OSError):
    def __init__(self, argv: Sequence[str], seconds: float) -> None:
        super().__init__(f"`{' '.join(argv)}` did not finish in {seconds:g}s")


class FeatureUnknownError(ValueError):
    def __init__(self, slice_id: str) -> None:
        super().__init__(f"the feature of {slice_id} is unknown, so its run cannot be launched")


class OrderRefusedError(ValueError):
    def __init__(self, outcome: ProcessOutcome, argv: Sequence[str]) -> None:
        super().__init__(outcome.stderr or outcome.stdout or f"`{' '.join(argv)}` exited {outcome.exit_code}")


class ServerDidNotStartError(OSError):
    def __init__(self, seconds: float) -> None:
        super().__init__(f"the herdr server did not answer within {seconds:g}s of being started")


class AgentNameTakenError(OSError):
    def __init__(self, name: str) -> None:
        super().__init__(f"the agent name `{name}` is already used")


class NoFreeAgentNameError(OSError):
    def __init__(self, candidates: Sequence[str]) -> None:
        super().__init__(f"every agent name tried is already used: {', '.join(candidates)}")


class MountingFailedError(OSError):
    def __init__(self, step: MountingStep, reason: str) -> None:
        super().__init__(f"the step `{step}` failed: {reason}")
        self.step = step
        self.reason = reason


class MountingAndCleanupFailedError(MountingFailedError):
    def __init__(self, step: MountingStep, reason: str, cleanup_reason: str) -> None:
        super().__init__(step, reason)
        self.args = (f"{self.args[0]}; closing the workspace it created failed too: {cleanup_reason}",)
        self.cleanup_reason = cleanup_reason
