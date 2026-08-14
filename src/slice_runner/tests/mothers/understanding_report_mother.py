from __future__ import annotations

from typing import ClassVar


class UnderstandingReportMother:
    SUMMARY: ClassVar[str] = (
        "hoy el plan y el esbozo piden el mismo contenido cuando la slice es mecanica, asi que esta "
        "slice los funde en una unica lista ordenada de piezas con su firma, lo que hacen y por que"
    )
    SIGNATURE: ClassVar[str] = "UnderstandingPlanPieceReportPayload(ContractModel): signature, does, reason"
    DOES: ClassVar[str] = "una pieza ordenada del plan, con su firma, lo que hace ese cuerpo y su motivo"
    REASON: ClassVar[str] = "todo lo demas depende de que campos existen en el contrato"
    SECOND_SIGNATURE: ClassVar[str] = "UnderstandingBrief.TEXT"
    SECOND_DOES: ClassVar[str] = "describe summary y plan en vez de summary, steps y sketch"
    SECOND_REASON: ClassVar[str] = "el brief tiene que hablar del contrato que de verdad se le pide"

    @classmethod
    def valid(cls) -> dict[str, object]:
        return {
            "summary": cls.SUMMARY,
            "plan": [
                {"signature": cls.SIGNATURE, "does": cls.DOES, "reason": cls.REASON},
                {"signature": cls.SECOND_SIGNATURE, "does": cls.SECOND_DOES, "reason": cls.SECOND_REASON},
            ],
        }

    @classmethod
    def without(cls, key: str) -> dict[str, object]:
        return {name: value for name, value in cls.valid().items() if name != key}

    @classmethod
    def with_a_piece_missing_its_signature(cls) -> dict[str, object]:
        return cls.valid() | {"plan": [{"does": cls.DOES, "reason": cls.REASON}]}

    @classmethod
    def with_a_piece_missing_what_it_does(cls) -> dict[str, object]:
        return cls.valid() | {"plan": [{"signature": cls.SIGNATURE, "reason": cls.REASON}]}

    @classmethod
    def with_a_piece_missing_its_reason(cls) -> dict[str, object]:
        return cls.valid() | {"plan": [{"signature": cls.SIGNATURE, "does": cls.DOES}]}

    @classmethod
    def with_pieces(cls, count: int) -> dict[str, object]:
        piece = {"signature": cls.SIGNATURE, "does": cls.DOES, "reason": cls.REASON}

        return cls.valid() | {"plan": [piece] * count}
