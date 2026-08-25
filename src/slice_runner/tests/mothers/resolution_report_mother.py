from __future__ import annotations

from typing import ClassVar


class ResolutionReportMother:
    SUMMARY: ClassVar[str] = "shared.txt tenia dos ediciones de la misma linea; me quede con la version de la base."

    @classmethod
    def valid(cls) -> dict[str, object]:
        return {"summary": cls.SUMMARY}

    @classmethod
    def without(cls, key: str) -> dict[str, object]:
        return {name: value for name, value in cls.valid().items() if name != key}

    @classmethod
    def with_an_unknown_field(cls) -> dict[str, object]:
        return cls.valid() | {"paths": []}
