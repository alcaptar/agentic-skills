from __future__ import annotations

from typing import Self

from pydantic import Field

from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.json_schema import JsonSchema

_SUMMARY_MAX_LENGTH = 600
_STEP_REASON_MAX_LENGTH = 200
_SKETCH_MAX_LENGTH = 1600
_MAX_STEPS = 8


class UnderstandingStepReportPayload(ContractModel):
    description: str
    reason: str = Field(max_length=_STEP_REASON_MAX_LENGTH)


class UnderstandingReportPayload(ContractModel):
    summary: str = Field(max_length=_SUMMARY_MAX_LENGTH)
    steps: list[UnderstandingStepReportPayload] = Field(max_length=_MAX_STEPS)
    sketch: str = Field(max_length=_SKETCH_MAX_LENGTH)

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the harness did not emit the understanding the brief asked for", InvalidUnderstandingReportError
        )
