from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.metrics_log import MetricsLog
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.metrics_entry_payload import MetricsEntryPayload

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.clock import Clock
    from slice_runner.domain.closed_slice import ClosedSlice


class LocalMetricsLog(MetricsLog):
    LEDGER: ClassVar[tuple[str, ...]] = ("slice-runner", "metrics.jsonl")

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock

    def record(self, closed: ClosedSlice) -> None:
        line = self._line(closed)
        ledger = self._ledger()
        ledger.parent.mkdir(parents=True, exist_ok=True)

        with ledger.open("a", encoding="utf-8") as log:
            log.write(f"{line}\n")

    def _ledger(self) -> Path:
        return ClaudeConfig.root().joinpath(*self.LEDGER)

    def _line(self, closed: ClosedSlice) -> str:
        payload = MetricsEntryPayload.from_domain(closed, ts=self._clock.now().isoformat())

        return json.dumps(payload.to_contract(), ensure_ascii=False)
