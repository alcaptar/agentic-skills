from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.cited_sources import CitedSources
from slice_runner.infrastructure.counted_lines import CountedLines
from slice_runner.infrastructure.harness_invocation_runner import HarnessInvocation
from slice_runner.infrastructure.prior_art_block import PriorArtBlock
from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.domain.judge import Judge
    from slice_runner.domain.slice_under_review import SliceUnderReview
    from slice_runner.domain.source_reader import SourceReader


@dataclass(frozen=True, kw_only=True, slots=True)
class JudgeInvocation(HarnessInvocation):
    EXECUTABLE: ClassVar[str] = "claude"
    MODEL: ClassVar[str] = "opus"

    judge: Judge
    review: SliceUnderReview
    reader: SourceReader

    @property
    def cwd(self) -> str:
        return self.review.worktree

    @property
    def argv(self) -> list[str]:
        return [
            self.EXECUTABLE,
            "-p",
            "--model",
            self.MODEL,
            "--output-format",
            "stream-json",
            "--verbose",
            "--tools",
            ",".join(self.judge.tools),
            *self._grants_to_read,
            "--strict-mcp-config",
            "--setting-sources",
            "user",
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
                f"- repo: {review.repo}",
                f"- ruta del repo: {review.worktree}",
                *PriorArtBlock.of(review.prior_art),
                f"- senal: {review.signal}",
                f"- excluye: {review.excludes}",
                *CountedLines.of("criterios de aceptacion", review.criteria),
                *CitedSources.of(
                    "fuentes de convencion", reader=self.reader, worktree=review.worktree, sources=review.sources
                ),
                *CountedLines.of(
                    "checklist de slices del issue",
                    tuple(f"[{entry.state}] {entry.title}" for entry in review.checklist),
                ),
                *CountedLines.of("ficheros que toca la slice", review.diff.files),
                *CountedLines.of(
                    "directorios que puedes leer", tuple(str(directory) for directory in self.judge.readable)
                ),
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
