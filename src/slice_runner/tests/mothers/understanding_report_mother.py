from __future__ import annotations

from typing import ClassVar


class UnderstandingReportMother:
    REPORT: ClassVar[str] = (
        "El entendimiento viaja en un solo campo porque el arnes pierde la frontera entre parametros: "
        "el primero se traga su cierre y lo que viene detras.\n\n"
        "- infrastructure/understanding_report_payload.py: deja `report` como unico campo; "
        "todo lo demas depende de que campos existen en el contrato\n"
        "- infrastructure/claude_understanding.py: publica el texto tal cual en vez de componerlo; "
        "es quien escribe el comentario de la subissue"
    )

    @classmethod
    def valid(cls) -> dict[str, object]:
        return {"report": cls.REPORT}

    @classmethod
    def without(cls, key: str) -> dict[str, object]:
        return {name: value for name, value in cls.valid().items() if name != key}

    @classmethod
    def blank(cls) -> dict[str, object]:
        return {"report": "   \n  "}

    @classmethod
    def with_an_unknown_field(cls) -> dict[str, object]:
        return cls.valid() | {"plan": []}
