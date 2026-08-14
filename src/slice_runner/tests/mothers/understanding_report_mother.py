from __future__ import annotations

from typing import ClassVar


class UnderstandingReportMother:
    SUMMARY: ClassVar[str] = (
        "hoy el esbozo llega como un texto libre que nadie envuelve, asi que markdown se come su "
        "indentacion; esta slice lo convierte en una lista de piezas y deja que el programa componga "
        "el bloque de codigo"
    )
    STEP_DESCRIPTION: ClassVar[str] = "infrastructure/understanding_report_payload.py"
    STEP_REASON: ClassVar[str] = "todo lo demas depende de que campos y minimos existen"
    SECOND_STEP_DESCRIPTION: ClassVar[str] = "infrastructure/claude_understanding.py"
    SECOND_STEP_REASON: ClassVar[str] = "es quien compone el texto que se publica en la subissue"
    SIGNATURE: ClassVar[str] = "UnderstandingPieceReportPayload(ContractModel): signature, does"
    DOES: ClassVar[str] = "una pieza del esbozo, con su firma y lo que hace ese cuerpo"

    @classmethod
    def valid(cls) -> dict[str, object]:
        return {
            "summary": cls.SUMMARY,
            "steps": [
                {"description": cls.STEP_DESCRIPTION, "reason": cls.STEP_REASON},
                {"description": cls.SECOND_STEP_DESCRIPTION, "reason": cls.SECOND_STEP_REASON},
            ],
            "sketch": [{"signature": cls.SIGNATURE, "does": cls.DOES}],
        }

    @classmethod
    def without(cls, key: str) -> dict[str, object]:
        return {name: value for name, value in cls.valid().items() if name != key}

    @classmethod
    def with_a_step_missing_its_reason(cls) -> dict[str, object]:
        return cls.valid() | {"steps": [{"description": cls.STEP_DESCRIPTION}] * 2}

    @classmethod
    def with_a_piece_missing_what_it_does(cls) -> dict[str, object]:
        return cls.valid() | {"sketch": [{"signature": cls.SIGNATURE}]}

    @classmethod
    def with_steps(cls, count: int) -> dict[str, object]:
        step = {"description": cls.STEP_DESCRIPTION, "reason": cls.STEP_REASON}

        return cls.valid() | {"steps": [step] * count}

    @classmethod
    def with_pieces(cls, count: int) -> dict[str, object]:
        piece = {"signature": cls.SIGNATURE, "does": cls.DOES}

        return cls.valid() | {"sketch": [piece] * count}

    @classmethod
    def filled_with_placeholders(cls) -> dict[str, object]:
        return {
            "summary": "test",
            "steps": [{"description": "a", "reason": "b"}],
            "sketch": [{"signature": "test", "does": "test"}],
        }
