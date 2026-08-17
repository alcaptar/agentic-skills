from __future__ import annotations

from typing import ClassVar

from slice_runner.domain.malformed_reason import MalformedReason
from slice_runner.infrastructure.automation_mark import AutomationMark


class MalformedResponseComment:
    MARKER: ClassVar[str] = "<!-- slice-runner:respuesta-mal-escrita -->"

    @classmethod
    def rendered(cls, reason: MalformedReason) -> str:
        return "\n\n".join(
            [f"No se pudo interpretar la respuesta: {cls._explanation(reason)}", cls.MARKER, AutomationMark.TEXT]
        )

    @classmethod
    def is_the_marker(cls, body: str) -> bool:
        return cls.MARKER in body

    @staticmethod
    def _explanation(reason: MalformedReason) -> str:
        match reason:
            case MalformedReason.GO_CARRIES_TEXT:
                return "`-GO` no lleva texto detras; escribe solo `-GO`."
            case MalformedReason.MISSING_CORRECTION:
                return "a `-REVIEW` le falta la correccion detras."
            case MalformedReason.MISSING_INSTRUCTION:
                return "a `-RETRY` le falta la instruccion detras."
            case MalformedReason.MISSING_CHANGE:
                return "a `-CHANGE` le falta detras lo que hay que cambiar."
