from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.counted_lines import CountedLines
from slice_runner.infrastructure.prior_art_block import PriorArtBlock
from slice_runner.infrastructure.understanding_brief import UnderstandingBrief
from slice_runner.infrastructure.understanding_report_payload import UnderstandingReportPayload

if TYPE_CHECKING:
    from slice_runner.domain.alignment import Alignment
    from slice_runner.domain.controls import Controls
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class UnderstandingInvocation:
    EXECUTABLE: ClassVar[str] = "claude"
    MODEL: ClassVar[str] = "sonnet"

    subissue: SubIssue
    parent: ParentIssue
    repo: str
    worktree: str
    alignment: Alignment

    @property
    def cwd(self) -> str:
        return self.worktree

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
            ",".join(UnderstandingBrief.TOOLS),
            "--strict-mcp-config",
            "--json-schema",
            json.dumps(UnderstandingReportPayload.json_schema(), ensure_ascii=False),
        ]

    @property
    def text(self) -> str:
        sections = [UnderstandingBrief.TEXT, "", self._slice_data]
        if self.alignment.agreed.strip():
            sections.extend(["", self._agreed])
        if self.alignment.correction.strip():
            sections.extend(["", self._correction])

        return "\n".join(sections)

    @property
    def _agreed(self) -> str:
        return "\n".join(
            [
                "## Lo acordado hasta ahora",
                "",
                "Es el entendimiento que ya se publico, con las correcciones anteriores dentro. Reescribelo",
                "entero aplicando la correccion nueva, y **conserva lo demas**: lo que no se corrige sigue acordado.",
                "",
                self.alignment.agreed,
            ]
        )

    @property
    def _correction(self) -> str:
        return "\n".join(["## Correccion pedida", "", self.alignment.correction])

    @property
    def _slice_data(self) -> str:
        subissue = self.subissue

        return "\n".join(
            [
                "## Datos de la slice",
                "",
                f"- issue: #{subissue.number}",
                f"- slice: {subissue.slice_id}",
                f"- repo: {self.repo}",
                f"- rama: {subissue.branch}",
                f"- ruta del repo: {self.worktree}",
                f"- intencion: {subissue.intention}",
                *PriorArtBlock.of(self.parent.prior_art),
                f"- senal: {subissue.signal}",
                *CountedLines.of("criterios de aceptacion", subissue.criteria),
                *CountedLines.of(
                    "fuentes de convencion", tuple(f"{source.kind}: {source.path}" for source in self.parent.sources)
                ),
                *self._controls,
            ]
        )

    @property
    def _controls(self) -> list[str]:
        return self._controls_of(self.parent.controls)

    @classmethod
    def _controls_of(cls, controls: Controls) -> list[str]:
        if controls.exemption_reason is not None:
            return [f"- controles del repo: ninguno - {controls.exemption_reason}"]

        return CountedLines.of(
            "controles del repo", tuple(f"{control.name}: {control.command}" for control in controls.commands)
        )
