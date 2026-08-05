from __future__ import annotations

from dataclasses import dataclass

_INTENTION_HEADING = "## Intencion"
_CRITERIA_HEADING = "## Criterios de aceptacion cumplidos"
_DEBT_HEADING = "## Deuda aceptada"
_SIGNAL_HEADING = "## Senal a comprobar tras el despliegue"


@dataclass(frozen=True, kw_only=True, slots=True)
class PullRequestBody:
    intention: str
    criteria: tuple[str, ...]
    debt: tuple[str, ...]
    signal: str
    subissue: int

    def rendered(self) -> str:
        sections = [
            self._section(_INTENTION_HEADING, self.intention),
            self._section(_CRITERIA_HEADING, self._bullets(self.criteria)),
            *([self._section(_DEBT_HEADING, self._bullets(self.debt))] if self.debt else []),
            self._section(_SIGNAL_HEADING, self.signal),
            f"Closes #{self.subissue}",
        ]

        return "\n\n".join(sections)

    @staticmethod
    def _section(heading: str, text: str) -> str:
        return f"{heading}\n{text}"

    @staticmethod
    def _bullets(lines: tuple[str, ...]) -> str:
        return "\n".join(f"- {line}" for line in lines)
