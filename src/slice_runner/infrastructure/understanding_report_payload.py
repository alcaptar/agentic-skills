from __future__ import annotations

from typing import Self

from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.json_schema import JsonSchema


class UnderstandingPlanPieceReportPayload(ContractModel):
    signature: str
    does: str
    reason: str


class UnderstandingReportPayload(ContractModel):
    summary: str
    plan: list[UnderstandingPlanPieceReportPayload]

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the harness did not emit the understanding the brief asked for", InvalidUnderstandingReportError
        )
