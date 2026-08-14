from __future__ import annotations

from typing import Self

from pydantic import Field

from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.json_schema import JsonSchema

_REPORT = (
    "El informe entero, en markdown y en un solo campo. Abre con dos o tres frases de como entiendes la "
    "slice, en tus propias palabras. Sigue con el plan, una linea por pieza y en el orden en que las vas "
    "a tocar: la firma de la clase, el metodo o la funcion -o la ruta, cuando todavia no haya firma que "
    "dar-, que hace ese cuerpo, y por que se toca. Nunca codigo pegable: quien revise tiene que ver la "
    "forma antes de que exista."
)


class UnderstandingReportPayload(ContractModel):
    report: str = Field(description=_REPORT)

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the harness did not emit the understanding the brief asked for", InvalidUnderstandingReportError
        )
