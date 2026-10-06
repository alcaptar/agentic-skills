from __future__ import annotations

from slice_panel.infrastructure.process_outcome import ProcessOutcome


class OutcomeMother:
    @staticmethod
    def succeeded(stdout: str = "") -> ProcessOutcome:
        return ProcessOutcome(exit_code=0, stdout=stdout, stderr="")

    @staticmethod
    def failed(stderr: str, *, exit_code: int = 1) -> ProcessOutcome:
        return ProcessOutcome(exit_code=exit_code, stdout="", stderr=stderr)
