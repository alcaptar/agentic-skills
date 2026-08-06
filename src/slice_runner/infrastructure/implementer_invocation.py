from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.report_payload import ImplementationReportPayload
from slice_runner.infrastructure.slice_implementer_brief import SliceImplementerBrief

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.finding import Finding


@dataclass(frozen=True, kw_only=True, slots=True)
class ImplementerInvocation:
    EXECUTABLE: ClassVar[str] = "claude"

    assignment: Assignment

    @property
    def cwd(self) -> str:
        return self.assignment.repo

    @property
    def argv(self) -> list[str]:
        return [
            self.EXECUTABLE,
            "-p",
            "--output-format",
            "json",
            "--permission-mode",
            "bypassPermissions",
            "--tools",
            ",".join(SliceImplementerBrief.TOOLS),
            "--strict-mcp-config",
            "--json-schema",
            json.dumps(ImplementationReportPayload.json_schema(), ensure_ascii=False),
        ]

    @property
    def text(self) -> str:
        return "\n".join([SliceImplementerBrief.TEXT, "", self._slice_data])

    @property
    def _slice_data(self) -> str:
        assignment = self.assignment

        return "\n".join(
            [
                "## Datos de la slice",
                "",
                f"- issue: #{assignment.issue}",
                f"- slice: {assignment.slice_id}",
                f"- ruta del repo: {assignment.repo}",
                f"- intencion: {assignment.intention}",
                f"- senal: {assignment.signal}",
                *self._counted("criterios de aceptacion", assignment.criteria),
                *self._counted(
                    "fuentes de convencion", tuple(f"{source.kind}: {source.path}" for source in assignment.sources)
                ),
                *self._controls,
                *self._findings,
                *self._control_logs,
            ]
        )

    @property
    def _controls(self) -> list[str]:
        controls = self.assignment.controls
        if controls.exemption_reason is not None:
            return [f"- controles del repo: ninguno - {controls.exemption_reason}"]

        return self._counted(
            "controles del repo", tuple(f"{control.name}: {control.command}" for control in controls.commands)
        )

    @property
    def _findings(self) -> list[str]:
        findings = self.assignment.findings
        if not findings:
            return ["- hallazgos de la vuelta anterior: ninguno, esta es la primera"]

        return self._counted("hallazgos de la vuelta anterior", tuple(self._raised(finding) for finding in findings))

    @property
    def _control_logs(self) -> list[str]:
        logs = self.assignment.control_logs
        if not logs:
            return []

        return self._counted("logs de los controles en rojo", tuple(str(log) for log in logs))

    @staticmethod
    def _raised(finding: Finding) -> str:
        where = f"{finding.path}:{finding.line}" if finding.line is not None else finding.path

        return f"[{finding.severity}] {finding.rule} en {where}: {finding.evidence} (detalle: {finding.detail})"

    @staticmethod
    def _counted(heading: str, entries: tuple[str, ...]) -> list[str]:
        return [f"- {heading} ({len(entries)}):", *(f"  - {entry}" for entry in entries)]
