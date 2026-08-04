from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.domain.judge_prompt import JudgePrompt


@dataclass(frozen=True, kw_only=True, slots=True)
class JudgeInvocation:
    EXECUTABLE: ClassVar[str] = "claude"
    TOOLS: ClassVar[tuple[str, ...]] = ("Read", "Grep", "Glob", "Skill")

    prompt: JudgePrompt

    @property
    def argv(self) -> list[str]:
        return [
            self.EXECUTABLE,
            "-p",
            "--output-format",
            "json",
            "--tools",
            ",".join(self.TOOLS),
            *self._grants_to_read,
            "--strict-mcp-config",
            "--json-schema",
            json.dumps(VerdictPayload.json_schema(), ensure_ascii=False),
        ]

    @property
    def text(self) -> str:
        return self.prompt.build()

    @property
    def _grants_to_read(self) -> list[str]:
        directories = [str(self.prompt.diff.diff.parent), self.prompt.repo]

        return [argument for directory in directories for argument in ("--add-dir", directory)]
