from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.domain.exceptions import UnreadableCallTraceError
from slice_runner.domain.step import Step
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.json_schema import JsonSchema

if TYPE_CHECKING:
    from slice_runner.domain.call_trace import HarnessCall


class HarnessCallPayload(ContractModel):
    slice_id: str
    step: Step
    session: str
    repo: str | None = None
    issue: int | None = None
    ts: str | None = None

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_call(cls, call: HarnessCall, *, ts: str) -> Self:
        return cls(
            slice_id=call.slice_id, step=call.step, session=call.session, repo=call.repo, issue=call.issue, ts=ts
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "the call trace line is not one this program wrote", UnreadableCallTraceError)
