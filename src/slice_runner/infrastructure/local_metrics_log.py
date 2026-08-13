from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.exceptions import UnreadableMetricsLogError
from slice_runner.domain.metrics_log import MetricsLog
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.metrics_entry_payload import MetricsEntryPayload
from slice_runner.infrastructure.metrics_ledger_entry import MetricsLedgerEntry

if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import datetime
    from pathlib import Path

    from slice_runner.domain.clock import Clock
    from slice_runner.domain.closed_slice import ClosedSlice
    from slice_runner.domain.closed_slice_record import ClosedSliceRecord


class LocalMetricsLog(MetricsLog):
    LEDGER: ClassVar[tuple[str, ...]] = ("slice-runner", "log", "metrics.jsonl")

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock

    def record(self, closed: ClosedSlice) -> None:
        line = self._line(closed)
        ledger = self._ledger()
        ledger.parent.mkdir(parents=True, exist_ok=True)

        with ledger.open("a", encoding="utf-8") as log:
            log.write(f"{line}\n")

    def closed_slices(self, *, repo: str | None, since: datetime, until: datetime) -> tuple[ClosedSliceRecord, ...]:
        ledger = self._ledger()
        if not ledger.exists():
            return ()

        return tuple(
            record
            for record in self._decoded(ledger.read_text(encoding="utf-8"))
            if since <= record.ts <= until and (repo is None or record.repo == repo)
        )

    @staticmethod
    def _decoded(text: str) -> Iterator[ClosedSliceRecord]:
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise UnreadableMetricsLogError(f"the metrics log has a line that is not JSON: {error}") from error
            if not isinstance(row, dict):
                raise UnreadableMetricsLogError(f"a metrics log line has to be an object, not {type(row).__name__}")

            record = MetricsLedgerEntry.read({str(key): value for key, value in row.items()})
            if record is not None:
                yield record

    def _ledger(self) -> Path:
        return ClaudeConfig.root().joinpath(*self.LEDGER)

    def _line(self, closed: ClosedSlice) -> str:
        payload = MetricsEntryPayload.from_domain(closed, ts=self._clock.now().isoformat())

        return json.dumps(payload.to_contract(), ensure_ascii=False)
