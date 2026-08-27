from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.call_spend_log import CallSpendLog
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.infrastructure.call_spend_payload import CallSpendPayload
from slice_runner.infrastructure.durable_ledger import DurableLedger

if TYPE_CHECKING:
    from collections.abc import Iterator

    from slice_runner.domain.call_spend_log import HarnessCallSpend
    from slice_runner.domain.clock import Clock


class LocalCallSpendLog(CallSpendLog):
    LEDGER: ClassVar[str] = "spend"

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock
        self._ledger: DurableLedger[CallSpendPayload] = DurableLedger(name=self.LEDGER, row=CallSpendPayload)

    def record(self, call: HarnessCallSpend) -> None:
        payload = CallSpendPayload.from_call(call, ts=self._clock.now().isoformat())
        self._ledger.append(payload)

    def spend_of(self, sessions: tuple[str, ...]) -> HarnessSpend:
        wanted = frozenset(sessions)

        return HarnessSpend.summing(self._once_per_session(self._ledger.rows(CallSpendPayload), wanted=wanted))

    @staticmethod
    def _once_per_session(calls: Iterator[CallSpendPayload], *, wanted: frozenset[str]) -> Iterator[HarnessSpend]:
        counted: set[str] = set()
        for call in calls:
            if call.session not in wanted or call.session in counted:
                continue
            counted.add(call.session)

            yield call.spend.to_domain()
