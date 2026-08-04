from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.domain.verification_request import VerificationRequest


@dataclass(frozen=True, kw_only=True, slots=True)
class JudgeInvocation:
    EXECUTABLE: ClassVar[str] = "claude"
    TOOLS: ClassVar[tuple[str, ...]] = ("Read", "Grep", "Glob", "Skill")

    request: VerificationRequest

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
    def prompt(self) -> str:
        diff = self.request.diff

        return "\n".join(
            [
                self.request.instructions,
                "",
                "## Datos del run",
                "",
                f"- ruta del repo: {self.request.repo}",
                f"- `slice.diff`: {diff.diff}",
                f"- ficheros que toca la slice ({len(diff.files)}):",
                *(f"  - {path}" for path in diff.files),
            ]
        )

    @property
    def _grants_to_read(self) -> list[str]:
        directories = [str(self.request.diff.diff.parent), self.request.repo]

        return [argument for directory in directories for argument in ("--add-dir", directory)]
