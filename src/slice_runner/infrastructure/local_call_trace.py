from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.call_trace import CallTrace
from slice_runner.domain.exceptions import UnreadableCallTraceError
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.harness_call_payload import HarnessCallPayload

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.call_trace import HarnessCall
    from slice_runner.domain.step import Step


class LocalCallTrace(CallTrace):
    LEDGER: ClassVar[tuple[str, ...]] = ("slice-runner", "trace", "calls.jsonl")

    def record(self, call: HarnessCall) -> None:
        ledger = self._ledger()
        ledger.parent.mkdir(parents=True, exist_ok=True)

        with ledger.open("a", encoding="utf-8") as trace:
            trace.write(f"{self._line(call)}\n")

    def sessions_of(self, *, slice_id: str, step: Step) -> tuple[str, ...]:
        ledger = self._ledger()
        if not ledger.exists():
            return ()

        calls = (self._decoded(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip())

        return tuple(call.session for call in calls if call.slice_id == slice_id and call.step == step)

    def _ledger(self) -> Path:
        return ClaudeConfig.root().joinpath(*self.LEDGER)

    @staticmethod
    def _decoded(line: str) -> HarnessCallPayload:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            raise UnreadableCallTraceError(f"the call trace has a line that is not JSON: {error}") from error
        if not isinstance(data, dict):
            raise UnreadableCallTraceError(f"a call trace line has to be an object, not {type(data).__name__}")

        return HarnessCallPayload.from_dict(data)

    @staticmethod
    def _line(call: HarnessCall) -> str:
        return json.dumps(HarnessCallPayload.from_call(call).to_contract(), ensure_ascii=False)
