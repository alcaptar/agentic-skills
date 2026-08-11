from __future__ import annotations

from typing import ClassVar

from slice_runner.infrastructure.automation_mark import AutomationMark


class ReopenedComment:
    MARKER: ClassVar[str] = "<!-- slice-runner:reabierta -->"

    @classmethod
    def rendered(cls, instruction: str) -> str:
        return "\n\n".join(
            [f"Slice reabierta por esta instruccion de reintento:\n\n{instruction}", cls.MARKER, AutomationMark.TEXT]
        )

    @classmethod
    def is_the_marker(cls, body: str) -> bool:
        return cls.MARKER in body
