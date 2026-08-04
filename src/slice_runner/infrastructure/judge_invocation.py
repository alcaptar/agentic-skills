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
            "--add-dir",
            self.prompt.repo,
            "--strict-mcp-config",
            "--json-schema",
            json.dumps(VerdictPayload.json_schema(), ensure_ascii=False),
        ]

    @property
    def text(self) -> str:
        return "\n".join([self.prompt.rubric, "", self._run_data, "", self._diff])

    @property
    def _run_data(self) -> str:
        files = self.prompt.diff.files

        return "\n".join(
            [
                "## Datos del run",
                "",
                f"- ruta del repo: {self.prompt.repo}",
                f"- ficheros que toca la slice ({len(files)}):",
                *(f"  - {path}" for path in files),
            ]
        )

    @property
    def _diff(self) -> str:
        return "\n".join(
            [
                "## Diff de la slice",
                "",
                "Empieza en la linea siguiente, tal cual lo emitio git, y cierra el prompt: no hay nada despues.",
                "",
                self.prompt.diff.text,
            ]
        )
