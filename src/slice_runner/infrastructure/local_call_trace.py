from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.call_trace import CallTrace
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.harness_call_payload import HarnessCallPayload

if TYPE_CHECKING:
    from slice_runner.infrastructure.call_trace import HarnessCall


class LocalCallTrace(CallTrace):
    LEDGER: ClassVar[tuple[str, ...]] = ("slice-runner", "trace", "calls.jsonl")

    def record(self, call: HarnessCall) -> None:
        ledger = ClaudeConfig.root().joinpath(*self.LEDGER)
        ledger.parent.mkdir(parents=True, exist_ok=True)

        with ledger.open("a", encoding="utf-8") as trace:
            trace.write(f"{self._line(call)}\n")

    @staticmethod
    def _line(call: HarnessCall) -> str:
        return json.dumps(HarnessCallPayload.from_call(call).to_contract(), ensure_ascii=False)
