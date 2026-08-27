from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.call_trace import CallTrace, HarnessCall
from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.infrastructure.durable_ledger import DurableLedger
from slice_runner.infrastructure.harness_call_payload import HarnessCallPayload

if TYPE_CHECKING:
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.step import Step


class LocalCallTrace(CallTrace):
    LEDGER: ClassVar[str] = "calls"

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock
        self._ledger: DurableLedger[HarnessCallPayload] = DurableLedger(name=self.LEDGER, row=HarnessCallPayload)

    def record(self, call: HarnessCall) -> None:
        payload = HarnessCallPayload.from_call(call, ts=self._clock.now().isoformat())
        self._ledger.append(payload)

    def sessions_of(self, *, repo: str, issue: int, slice_id: str, step: Step) -> tuple[str, ...]:
        return tuple(
            call.session
            for call in self._ledger.rows(HarnessCallPayload)
            if call.repo == repo and call.issue == issue and call.slice_id == slice_id and call.step == step
        )

    def calls_of(self, *, repo: str, issue: int, slice_id: str) -> tuple[HarnessCall, ...]:
        coordinates = SliceCoordinates(repo=repo, issue=issue, slice_id=CanonicalSliceId.of_text(slice_id))
        wanted = coordinates.slice_id.text

        return tuple(
            HarnessCall(coordinates=coordinates, step=call.step, session=call.session)
            for call in self._ledger.rows(HarnessCallPayload)
            if call.repo == coordinates.repo and call.issue == coordinates.issue and call.slice_id == wanted
        )
