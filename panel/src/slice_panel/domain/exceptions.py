from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

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
