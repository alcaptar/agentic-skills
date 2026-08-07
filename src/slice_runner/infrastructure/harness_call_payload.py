from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.domain.step import Step
from slice_runner.infrastructure.contract_model import ContractModel

if TYPE_CHECKING:
    from slice_runner.infrastructure.call_trace import HarnessCall


class HarnessCallPayload(ContractModel):
    slice_id: str
    step: Step
    session: str

    @classmethod
    def from_call(cls, call: HarnessCall) -> Self:
        return cls(slice_id=call.slice_id, step=call.step, session=call.session)
