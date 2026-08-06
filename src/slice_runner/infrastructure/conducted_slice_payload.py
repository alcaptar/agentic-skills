from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.domain.halt import Halt
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step
from slice_runner.infrastructure.contract_model import ContractModel

if TYPE_CHECKING:
    from slice_runner.application.actions.conduct_slice import ConductSliceResult


class ConductedSlicePayload(ContractModel):
    halt: Halt
    state: RunState
    step: Step
    precheck: PrecheckOutcome | None = None
    pull_request: int | None = None

    @classmethod
    def from_domain(cls, conducted: ConductSliceResult) -> Self:
        return cls(
            halt=conducted.halt,
            state=conducted.state,
            step=conducted.step,
            precheck=conducted.precheck,
            pull_request=conducted.pull_request,
        )
