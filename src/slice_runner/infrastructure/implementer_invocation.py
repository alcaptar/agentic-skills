from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.counted_lines import CountedLines
from slice_runner.infrastructure.report_payload import ImplementationReportPayload
from slice_runner.infrastructure.slice_implementer_brief import SliceImplementerBrief

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.finding import Finding


@dataclass(frozen=True, kw_only=True, slots=True)
class ImplementerInvocation:
    EXECUTABLE: ClassVar[str] = "claude"
    MODEL: ClassVar[str] = "sonnet"

    assignment: Assignment

    @property
    def cwd(self) -> str:
        return self.assignment.repo

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
                *CountedLines.of("criterios de aceptacion", assignment.criteria),
                *CountedLines.of(
                    "fuentes de convencion", tuple(f"{source.kind}: {source.path}" for source in assignment.sources)
                ),
                *self._controls,
                *self._findings,
                *self._control_logs,
                *self._hygiene_refusal,
                *self._understanding,
                *self._retry_instruction,
            ]
        )

    @property
    def _retry_instruction(self) -> list[str]:
        instruction = self.assignment.retry_instruction.strip()
        if not instruction:
            return []

        return [
            "",
            "## Instruccion de reintento",
            "",
            "Esta slice estaba bloqueada o abortada; una persona la reabrio con esta instruccion, que gana a lo",
            "que hicieras antes del bloqueo:",
            "",
            instruction,
        ]

    @property
    def _understanding(self) -> list[str]:
        agreed = self.assignment.understanding.strip()
        if not agreed:
            return []

        return [
            "",
            "## Entendimiento acordado",
            "",
            "Es el plan que una persona reviso y aprobo antes de que empezaras. Donde lo contradigan,",
            "las convenciones del repo y los criterios de aceptacion ganan; en lo demas, esto es lo acordado.",
            "",
            agreed,
        ]

    @property
    def _controls(self) -> list[str]:
        controls = self.assignment.controls
        if controls.exemption_reason is not None:
            return [f"- controles del repo: ninguno - {controls.exemption_reason}"]

        return CountedLines.of(
            "controles del repo", tuple(f"{control.name}: {control.command}" for control in controls.commands)
        )

    @property
    def _findings(self) -> list[str]:
        findings = self.assignment.findings
        if not findings:
            return ["- hallazgos de la vuelta anterior: ninguno, esta es la primera"]

        return CountedLines.of("hallazgos de la vuelta anterior", tuple(self._raised(finding) for finding in findings))

    @property
    def _control_logs(self) -> list[str]:
        logs = self.assignment.control_logs
        if not logs:
            return []

        return CountedLines.of("logs de los controles en rojo", tuple(str(log) for log in logs))

    @property
    def _hygiene_refusal(self) -> list[str]:
        refusal = self.assignment.hygiene_refusal
        if not refusal:
            return []

        return [
            "- la vuelta anterior no llego a medirse: el indice quedo sucio y los controles no se ejecutaron",
            f"  - {refusal}",
            "  - declara en tu informe TODO fichero que toques, o no lo toques",
        ]

    @staticmethod
    def _raised(finding: Finding) -> str:
        where = f"{finding.path}:{finding.line}" if finding.line is not None else finding.path

        return f"[{finding.severity}] {finding.rule} en {where}: {finding.evidence} (detalle: {finding.detail})"
