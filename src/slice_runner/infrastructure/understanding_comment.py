from __future__ import annotations

from typing import ClassVar

_HOW_TO_RESPOND = (
    "Para continuar, responde a este comentario:\n"
    "\n"
    "- `-GO` arranca la implementacion tal como queda descrita arriba.\n"
    "- `-REVIEW <correccion>` vuelve a redactar el entendimiento con esa correccion y lo publica de nuevo.\n"
    "\n"
    "Sin respuesta la slice se queda esperando: reinvocar no vuelve a publicar el entendimiento."
)


class UnderstandingComment:
    MARKER: ClassVar[str] = "<!-- slice-runner:entendimiento -->"

    @classmethod
    def rendered(cls, text: str) -> str:
        return "\n\n".join([text, _HOW_TO_RESPOND, cls.MARKER])

    @classmethod
    def is_the_understanding(cls, body: str) -> bool:
        return cls.MARKER in body

    @classmethod
    def written_in(cls, body: str) -> str:
        return body.split(_HOW_TO_RESPOND, maxsplit=1)[0].strip()
