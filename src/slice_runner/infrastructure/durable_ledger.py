from __future__ import annotations

import json
from abc import abstractmethod
from typing import TYPE_CHECKING, ClassVar, Generic, Self, TypeVar

from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.contract_model import ContractModel

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path


class LedgerRow(ContractModel):
    pass


class ReadableLedgerRow(LedgerRow):
    UNREADABLE: ClassVar[type[ValueError]]

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, object]) -> Self: ...


_Row = TypeVar("_Row", bound=LedgerRow)
_Read = TypeVar("_Read", bound=ReadableLedgerRow)


class DurableLedger(Generic[_Row]):
    def __init__(self, *, name: str, row: type[_Row]) -> None:
        self._name = name

    def path(self) -> Path:
        return ClaudeConfig.root() / "slice-runner" / "runs" / f"{self._name}.jsonl"

    def append(self, row: _Row) -> None:
        ledger = self.path()
        ledger.parent.mkdir(parents=True, exist_ok=True)

        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(f"{json.dumps(row.to_contract(), ensure_ascii=False)}\n")

    def rows(self, as_row: type[_Read]) -> Iterator[_Read]:
        yield from self.rows_where(as_row, self._anything)

    def rows_where(self, as_row: type[_Read], keep: Callable[[dict[str, object]], bool]) -> Iterator[_Read]:
        for number, line in self._numbered_lines():
            data = self._decoded(line, number, as_row)
            if not keep(data):
                continue

            yield as_row.from_dict(data)

    @staticmethod
    def _anything(data: dict[str, object]) -> bool:
        return True

    def _numbered_lines(self) -> Iterator[tuple[int, str]]:
        ledger = self.path()
        if not ledger.exists():
            return

        for number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip():
                yield number, line

    def _decoded(self, line: str, number: int, as_row: type[_Read]) -> dict[str, object]:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            raise as_row.UNREADABLE(
                f"the {self._name} ledger has a line at {number} that is not JSON: {error}"
            ) from error
        if not isinstance(data, dict):
            raise as_row.UNREADABLE(
                f"the {self._name} ledger has a line at {number} that has to be an object, not {type(data).__name__}"
            )

        return {str(key): value for key, value in data.items()}
