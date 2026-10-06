from __future__ import annotations

from typing import ClassVar

from slice_runner.infrastructure.automation_mark import AutomationMark

_HOW_TO_RESPOND_OPENING = "Para continuar, "
_HOW_TO_RESPOND = (
    f"{_HOW_TO_RESPOND_OPENING}da una orden con `slice-runner` y vuelve a lanzar `run`:\n"
    "\n"
    "- `slice-runner go <subissue> --repo <org>/<repo>` acuerda el entendimiento tal como queda descrito arriba.\n"
    "- `slice-runner review <subissue> --repo <org>/<repo> <correccion>` pide rehacer el entendimiento con esa "
    "correccion.\n"
    "\n"
    "Tambien vale responder a este comentario con `-GO` o con `-REVIEW <correccion>`: el siguiente `run` lo lee.\n"
    "\n"
    "Sin orden la slice se queda esperando: lanzar `run` no vuelve a publicar el entendimiento."
)


class UnderstandingComment:
    MARKER: ClassVar[str] = "<!-- slice-runner:entendimiento -->"

    @classmethod
    def rendered(cls, text: str) -> str:
        return "\n\n".join([text, _HOW_TO_RESPOND, cls.MARKER, AutomationMark.TEXT])

    @classmethod
    def is_the_understanding(cls, body: str) -> bool:
        return cls.MARKER in body

    @classmethod
    def written_in(cls, body: str) -> str:
        return body.split(f"\n\n{_HOW_TO_RESPOND_OPENING}", maxsplit=1)[0].strip()
