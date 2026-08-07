from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.finding import Finding

_INTENTION_HEADING = "## Intencion"
_INFERRED_INTENTION_HEADING = "## Intencion (inferida del issue, no declarada)"
_CRITERIA_HEADING = "## Criterios de aceptacion cumplidos"
_DEBT_HEADING = "## Deuda aceptada"
_SIGNAL_HEADING = "## Senal a comprobar tras el despliegue"


@dataclass(frozen=True, kw_only=True, slots=True)
class PullRequestBody:
    intention: str
    criteria: tuple[str, ...]
    debt: tuple[str, ...]
    findings: tuple[Finding, ...]
    signal: str
    subissue: int

    def rendered(self) -> str:
        debt = (*self.debt, *(self._finding_line(finding) for finding in self.findings))
        sections = [
            self._section(self._intention_heading, self.intention),
            self._section(_CRITERIA_HEADING, self._bullets(self.criteria)),
            *([self._section(_DEBT_HEADING, self._bullets(debt))] if debt else []),
            self._section(_SIGNAL_HEADING, self.signal),
            f"Closes #{self.subissue}",
        ]

        return "\n\n".join(sections)

    @property
    def _intention_heading(self) -> str:
        return _INTENTION_HEADING if self.intention.strip() else _INFERRED_INTENTION_HEADING

    @staticmethod
    def _section(heading: str, text: str) -> str:
        return f"{heading}\n{text}"

    @staticmethod
    def _bullets(lines: tuple[str, ...]) -> str:
        return "\n".join(f"- {line}" for line in lines)

    @staticmethod
    def _finding_line(finding: Finding) -> str:
        return f"{finding.severity}: {finding.detail} ({finding.path})"
