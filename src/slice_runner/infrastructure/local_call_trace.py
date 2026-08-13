from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.call_trace import CallTrace, HarnessCall
from slice_runner.domain.exceptions import UnreadableCallTraceError
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.harness_call_payload import HarnessCallPayload

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.clock import Clock
    from slice_runner.domain.step import Step


class LocalCallTrace(CallTrace):
    LEDGER: ClassVar[tuple[str, ...]] = ("slice-runner", "trace", "calls.jsonl")

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock

    def record(self, call: HarnessCall) -> None:
        ledger = self._ledger()
        ledger.parent.mkdir(parents=True, exist_ok=True)

        with ledger.open("a", encoding="utf-8") as trace:
            trace.write(f"{self._line(call)}\n")

    def sessions_of(self, *, repo: str, issue: int, slice_id: str, step: Step) -> tuple[str, ...]:
        ledger = self._ledger()
        if not ledger.exists():
            return ()

        calls = (self._decoded(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip())

        return tuple(
            call.session
            for call in calls
            if call.repo == repo and call.issue == issue and call.slice_id == slice_id and call.step == step
        )

    def calls_of(self, *, repo: str, issue: int, slice_id: str) -> tuple[HarnessCall, ...]:
        ledger = self._ledger()
        if not ledger.exists():
            return ()

        calls = (self._decoded(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip())

        return tuple(
            HarnessCall(repo=repo, issue=issue, slice_id=slice_id, step=call.step, session=call.session)
            for call in calls
            if call.repo == repo and call.issue == issue and call.slice_id == slice_id
        )

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

    def _line(self, call: HarnessCall) -> str:
        payload = HarnessCallPayload.from_call(call, ts=self._clock.now().isoformat())

        return json.dumps(payload.to_contract(), ensure_ascii=False)
