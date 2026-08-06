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
        review = self.review

        return "\n".join(
            [
                "## Datos del run",
                "",
                f"- slice: {review.slice_id}",
                f"- ruta del repo: {review.repo}",
                f"- senal: {review.signal}",
                *self._counted("criterios de aceptacion", review.criteria),
                *self._counted(
                    "fuentes de convencion", tuple(f"{source.kind}: {source.path}" for source in review.sources)
                ),
                *self._counted(
                    "checklist de slices del issue",
                    tuple(f"[{entry.state}] {entry.title}" for entry in review.checklist),
                ),
                *self._counted("ficheros que toca la slice", review.diff.files),
                *self._counted(
                    "directorios que puedes leer", tuple(str(directory) for directory in self.judge.readable)
                ),
            ]
        )

    @staticmethod
    def _counted(heading: str, entries: tuple[str, ...]) -> list[str]:
        return [f"- {heading} ({len(entries)}):", *(f"  - {entry}" for entry in entries)]

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
