from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.claude_config import ClaudeConfig

if TYPE_CHECKING:
    from pathlib import Path


class ControlLogsDirectory:
    SEGMENTS: ClassVar[tuple[str, ...]] = ("slice-runner", "runs", "controls")

    @classmethod
    def default(cls) -> Path:
        return ClaudeConfig.root().joinpath(*cls.SEGMENTS)
