from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.domain.run_state import RunState
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.run_payload import RunPayload

if TYPE_CHECKING:
    from slice_runner.domain.transition import Transition


class TransitionPayload(ContractModel):
    run: RunPayload
    state: RunState
    wait_seconds: int

    @classmethod
    def from_domain(cls, transition: Transition) -> Self:
        return cls(
            run=RunPayload.from_domain(transition.run),
            state=transition.state,
            wait_seconds=transition.wait_seconds,
        )
