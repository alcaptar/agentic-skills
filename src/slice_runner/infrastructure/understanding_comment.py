from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.understanding_writer import UnderstandingWriter

if TYPE_CHECKING:
    from slice_runner.domain.controls import Controls
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.sub_issue import SubIssue

_HEADING = "## Entendimiento de la slice"
_WHY_THIS_ONE = "Es la primera del checklist que no esta cerrada, bloqueada ni abortada."
_INTENTION_HEADING = "### Intencion"
_CRITERIA_HEADING = "### Criterios de aceptacion"
_SIGNAL_HEADING = "### Senal"
_SOURCES_HEADING = "### Fuentes de convencion"
_CONTROLS_HEADING = "### Controles del repo"


class UnderstandingComment(UnderstandingWriter):
    def write(self, *, subissue: SubIssue, parent: ParentIssue, repo: str) -> str:
        sections = [
            _HEADING,
            subissue.title,
            _WHY_THIS_ONE,
            f"- repo: {repo}\n- rama: {subissue.branch}",
            self._section(_INTENTION_HEADING, subissue.intention),
            self._section(_CRITERIA_HEADING, self._bullets(subissue.criteria)),
            self._section(_SIGNAL_HEADING, subissue.signal),
            self._section(_SOURCES_HEADING, self._bullets(self._sources(parent))),
            self._section(_CONTROLS_HEADING, self._bullets(self._controls(parent.controls))),
        ]

        return "\n\n".join(sections) + "\n"

    @staticmethod
    def _section(heading: str, text: str) -> str:
        return f"{heading}\n\n{text}"

    @staticmethod
    def _bullets(lines: tuple[str, ...]) -> str:
        return "\n".join(f"- {line}" for line in lines)

    @staticmethod
    def _sources(parent: ParentIssue) -> tuple[str, ...]:
        return tuple(f"{source.kind}: {source.path}" for source in parent.sources)

    @staticmethod
    def _controls(controls: Controls) -> tuple[str, ...]:
        if controls.exemption_reason is not None:
            return (f"ninguno: {controls.exemption_reason}",)

        return tuple(f"{command.name}: {command.command}" for command in controls.commands)
