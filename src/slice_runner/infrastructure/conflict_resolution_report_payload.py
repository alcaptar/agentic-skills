from __future__ import annotations

from typing import Self

from pydantic import Field

from slice_runner.domain.exceptions import InvalidResolutionReportError
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.json_schema import JsonSchema

_SUMMARY = (
    "Un resumen breve, en un par de frases, de que conflicto era y como lo resolviste. Va dirigido a "
    "quien revise la conversacion despues, no es una promesa de exito: el programa comprueba el "
    "resultado en el arbol de trabajo, no en lo que digas aqui."
)


class ConflictResolutionReportPayload(ContractModel):
    summary: str = Field(description=_SUMMARY)

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the resolver did not emit the report the brief asked for", InvalidResolutionReportError
        )
