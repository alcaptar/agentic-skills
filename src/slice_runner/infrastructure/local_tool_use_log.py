from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.tool_use_log import ToolUseLog
from slice_runner.infrastructure.tool_use_payload import CallToolUsePayload

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.infrastructure.tool_use_log import HarnessCallToolUse


class LocalToolUseLog(ToolUseLog):
    LEDGER: ClassVar[tuple[str, ...]] = ("slice-runner", "trace", "tool-uses.jsonl")

    def record(self, call: HarnessCallToolUse) -> None:
        ledger = self._ledger()
        ledger.parent.mkdir(parents=True, exist_ok=True)

        with ledger.open("a", encoding="utf-8") as trace:
            trace.write(f"{self._line(call)}\n")

    def _ledger(self) -> Path:
        return ClaudeConfig.root().joinpath(*self.LEDGER)

    @staticmethod
    def _line(call: HarnessCallToolUse) -> str:
        return json.dumps(CallToolUsePayload.from_call(call).to_contract(), ensure_ascii=False)
