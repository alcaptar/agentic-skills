from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.tool_use_log import ToolUseLog
from slice_runner.infrastructure.tool_use_payload import CallToolUsePayload, UnrecordedCallToolUsePayload

if TYPE_CHECKING:
    from slice_runner.infrastructure.tool_use_log import HarnessCallToolUse, UnrecordedCallToolUse


class LocalToolUseLog(ToolUseLog):
    LEDGER: ClassVar[tuple[str, ...]] = ("slice-runner", "trace", "tool-uses.jsonl")
    UNRECORDED_LEDGER: ClassVar[tuple[str, ...]] = ("slice-runner", "trace", "unrecorded-tool-uses.jsonl")

    def record(self, call: HarnessCallToolUse) -> None:
        self._appended(self.LEDGER, json.dumps(CallToolUsePayload.from_call(call).to_contract(), ensure_ascii=False))

    def record_unrecorded(self, call: UnrecordedCallToolUse) -> None:
        self._appended(
            self.UNRECORDED_LEDGER,
            json.dumps(UnrecordedCallToolUsePayload.from_call(call).to_contract(), ensure_ascii=False),
        )

    @staticmethod
    def _appended(ledger_path: tuple[str, ...], line: str) -> None:
        ledger = ClaudeConfig.root().joinpath(*ledger_path)
        ledger.parent.mkdir(parents=True, exist_ok=True)

        with ledger.open("a", encoding="utf-8") as trace:
            trace.write(f"{line}\n")
