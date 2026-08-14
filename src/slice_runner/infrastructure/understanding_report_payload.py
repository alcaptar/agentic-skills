from __future__ import annotations

from typing import Self

from pydantic import Field

from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.json_schema import JsonSchema

_SUMMARY_MIN_LENGTH = 120
_STEP_DESCRIPTION_MIN_LENGTH = 15
_STEP_REASON_MIN_LENGTH = 15
_SIGNATURE_MIN_LENGTH = 10
_DOES_MIN_LENGTH = 15
_MIN_STEPS = 2
_MIN_PIECES = 1


class UnderstandingStepReportPayload(ContractModel):
    description: str = Field(min_length=_STEP_DESCRIPTION_MIN_LENGTH)
    reason: str = Field(min_length=_STEP_REASON_MIN_LENGTH)


class UnderstandingPieceReportPayload(ContractModel):
    signature: str = Field(min_length=_SIGNATURE_MIN_LENGTH)
    does: str = Field(min_length=_DOES_MIN_LENGTH)


class UnderstandingReportPayload(ContractModel):
    summary: str = Field(min_length=_SUMMARY_MIN_LENGTH)
    steps: list[UnderstandingStepReportPayload] = Field(min_length=_MIN_STEPS)
    sketch: list[UnderstandingPieceReportPayload] = Field(min_length=_MIN_PIECES)

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the harness did not emit the understanding the brief asked for", InvalidUnderstandingReportError
        )
