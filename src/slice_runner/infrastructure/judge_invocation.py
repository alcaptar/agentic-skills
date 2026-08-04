from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.domain.judge import Judge
    from slice_runner.domain.slice_under_review import SliceUnderReview


@dataclass(frozen=True, kw_only=True, slots=True)
class JudgeInvocation:
    EXECUTABLE: ClassVar[str] = "claude"

    judge: Judge
    review: SliceUnderReview

    @property
    def argv(self) -> list[str]:
        return [
            self.EXECUTABLE,
            "-p",
            "--output-format",
            "json",
            "--tools",
            ",".join(self.judge.tools),
            *self._grants_to_read,
            "--strict-mcp-config",
            "--json-schema",
            json.dumps(VerdictPayload.json_schema(), ensure_ascii=False),
        ]

    @property
    def text(self) -> str:
        return "\n".join([self.judge.rubric, "", self._run_data, "", self._diff])

    @property
    def _grants_to_read(self) -> list[str]:
        return [argument for directory in self.judge.readable for argument in ("--add-dir", str(directory))]

    @property
    def _run_data(self) -> str:
        files = self.review.diff.files

        return "\n".join(
            [
                "## Datos del run",
                "",
                f"- ruta del repo: {self.review.repo}",
                f"- ficheros que toca la slice ({len(files)}):",
                *(f"  - {path}" for path in files),
                f"- directorios que puedes leer ({len(self.judge.readable)}):",
                *(f"  - {directory}" for directory in self.judge.readable),
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
                self.review.diff.text,
            ]
        )
