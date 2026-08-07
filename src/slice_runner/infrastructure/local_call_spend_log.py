from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.call_spend_log import CallSpendLog
from slice_runner.domain.exceptions import UnreadableCallSpendLogError
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.infrastructure.call_spend_payload import CallSpendPayload
from slice_runner.infrastructure.claude_config import ClaudeConfig

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.call_spend_log import HarnessCallSpend


class LocalCallSpendLog(CallSpendLog):
    LEDGER: ClassVar[tuple[str, ...]] = ("slice-runner", "trace", "spend.jsonl")

    def record(self, call: HarnessCallSpend) -> None:
        ledger = self._ledger()
        ledger.parent.mkdir(parents=True, exist_ok=True)

        with ledger.open("a", encoding="utf-8") as trace:
            trace.write(f"{self._line(call)}\n")

    def spend_of(self, sessions: tuple[str, ...]) -> HarnessSpend:
        ledger = self._ledger()
        if not ledger.exists():
            return HarnessSpend.nothing()

        calls = (self._decoded(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip())

        return HarnessSpend.summing(call.spend.to_domain() for call in calls if call.session in sessions)

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

    @staticmethod
    def _line(call: HarnessCallSpend) -> str:
        return json.dumps(CallSpendPayload.from_call(call).to_contract(), ensure_ascii=False)
