from __future__ import annotations

from typing import Self

from pydantic import Field

from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.json_schema import JsonSchema

_SUMMARY = (
    "Como entiendes la slice, en tus propias palabras. Dos o tres frases y por debajo de 1000 caracteres: "
    "es el entendimiento, no el plan, que va entero en `plan` y no aqui."
)
_PLAN = (
    "El plan, pieza a pieza y en el orden en que las vas a tocar. Obligatorio y nunca vacio: un informe "
    "sin plan no es un informe, aunque el resumen sea largo."
)
_SIGNATURE = (
    "La firma de la clase, el metodo o la funcion, segun mande la convencion del repo, o la ruta que vas a "
    "tocar cuando todavia no haya firma que dar. Texto plano: nada de markdown, comillas ni indentacion."
)
_DOES = "Una linea con lo que hace ese cuerpo. Nunca codigo pegable: la forma antes de que exista."
_REASON = "Por que se toca eso, como campo propio y no como prosa dentro de `does`."


class UnderstandingPlanPieceReportPayload(ContractModel):
    signature: str = Field(description=_SIGNATURE)
    does: str = Field(description=_DOES)
    reason: str = Field(description=_REASON)


class UnderstandingReportPayload(ContractModel):
    summary: str = Field(description=_SUMMARY)
    plan: list[UnderstandingPlanPieceReportPayload] = Field(description=_PLAN)

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the harness did not emit the understanding the brief asked for", InvalidUnderstandingReportError
        )
