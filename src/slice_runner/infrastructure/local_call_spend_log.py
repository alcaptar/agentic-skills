from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.call_spend_log import CallSpendLog
from slice_runner.domain.exceptions import UnreadableCallSpendLogError
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.infrastructure.call_spend_payload import CallSpendPayload
from slice_runner.infrastructure.claude_config import ClaudeConfig

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from slice_runner.domain.call_spend_log import HarnessCallSpend
    from slice_runner.domain.clock import Clock


class LocalCallSpendLog(CallSpendLog):
    LEDGER: ClassVar[tuple[str, ...]] = ("slice-runner", "log", "spend.jsonl")

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock

    def record(self, call: HarnessCallSpend) -> None:
        ledger = self._ledger()
        ledger.parent.mkdir(parents=True, exist_ok=True)

        with ledger.open("a", encoding="utf-8") as trace:
            trace.write(f"{self._line(call)}\n")

    def spend_of(self, sessions: tuple[str, ...]) -> HarnessSpend:
        ledger = self._ledger()
        if not ledger.exists():
            return HarnessSpend.nothing()

        wanted = frozenset(sessions)
        calls = (self._decoded(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip())

        return HarnessSpend.summing(self._once_per_session(calls, wanted=wanted))

    @staticmethod
    def _once_per_session(calls: Iterator[CallSpendPayload], *, wanted: frozenset[str]) -> Iterator[HarnessSpend]:
        counted: set[str] = set()
        for call in calls:
            if call.session not in wanted or call.session in counted:
                continue
            counted.add(call.session)

            yield call.spend.to_domain()

    def _ledger(self) -> Path:
        return ClaudeConfig.root().joinpath(*self.LEDGER)

    @staticmethod
    def _decoded(line: str) -> CallSpendPayload:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            raise UnreadableCallSpendLogError(f"the spend log has a line that is not JSON: {error}") from error
        if not isinstance(data, dict):
            raise UnreadableCallSpendLogError(f"a spend log line has to be an object, not {type(data).__name__}")

        return CallSpendPayload.from_dict(data)

    def _line(self, call: HarnessCallSpend) -> str:
        payload = CallSpendPayload.from_call(call, ts=self._clock.now().isoformat())

        return json.dumps(payload.to_contract(), ensure_ascii=False)
