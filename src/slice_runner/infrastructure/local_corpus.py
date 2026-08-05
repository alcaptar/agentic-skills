from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.corpus import Corpus
from slice_runner.infrastructure.corpus_entry_payload import CorpusEntryPayload

if TYPE_CHECKING:
    from slice_runner.domain.corpus_entry import CorpusEntry


class LocalCorpus(Corpus):
    CONFIG_VARIABLE: ClassVar[str] = "CLAUDE_CONFIG_DIR"
    DEFAULT_CONFIG: ClassVar[str] = "~/.claude"
    LEDGER: ClassVar[tuple[str, ...]] = ("slice-runner", "corpus", "verdicts.jsonl")

    def record(self, entry: CorpusEntry) -> None:
        ledger = self._configured_root().joinpath(*self.LEDGER)
        ledger.parent.mkdir(parents=True, exist_ok=True)

        with ledger.open("a", encoding="utf-8") as corpus:
            corpus.write(f"{self._line(entry)}\n")

    def _configured_root(self) -> Path:
        return Path(os.environ.get(self.CONFIG_VARIABLE) or self.DEFAULT_CONFIG).expanduser()

    @staticmethod
    def _line(entry: CorpusEntry) -> str:
        return json.dumps(CorpusEntryPayload.from_domain(entry).to_contract(), ensure_ascii=False)
