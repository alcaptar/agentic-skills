from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.corpus import Corpus
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.corpus_diff_payload import CorpusDiffPayload
from slice_runner.infrastructure.corpus_verdict_payload import CorpusVerdictPayload

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.clock import Clock
    from slice_runner.domain.corpus_entry import CorpusEntry


class LocalCorpus(Corpus):
    LEDGER: ClassVar[tuple[str, ...]] = ("slice-runner", "log", "verdicts.jsonl")
    DIFF_LEDGER: ClassVar[tuple[str, ...]] = ("slice-runner", "log", "diffs.jsonl")

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock

    def record(self, entry: CorpusEntry) -> None:
        ts = self._clock.now().isoformat()
        self._appended(self._ledger(), CorpusVerdictPayload.from_domain(entry, ts=ts))
        self._appended(self._diff_ledger(), CorpusDiffPayload.from_domain(entry, ts=ts))

    def _ledger(self) -> Path:
        return ClaudeConfig.root().joinpath(*self.LEDGER)

    def _diff_ledger(self) -> Path:
        return ClaudeConfig.root().joinpath(*self.DIFF_LEDGER)

    @staticmethod
    def _appended(ledger: Path, payload: CorpusVerdictPayload | CorpusDiffPayload) -> None:
        ledger.parent.mkdir(parents=True, exist_ok=True)

        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(f"{json.dumps(payload.to_contract(), ensure_ascii=False)}\n")
