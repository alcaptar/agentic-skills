from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType

    import pytest

_Row = TypeVar("_Row")


class StubLedger(Generic[_Row]):
    def __init__(self, *, name: str, row: type[_Row]) -> None:
        self.name = name
        self.row = row
        self.appended: list[_Row] = []

    def append(self, row: _Row) -> None:
        self.appended.append(row)

    def rows(self, as_row: type[object]) -> Iterator[_Row]:
        yield from self.appended


class WiredStubLedgers:
    _PATCHED_NAMES = ("DurableLedger",)

    @staticmethod
    def on(module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> list[StubLedger[Any]]:
        created: list[StubLedger[Any]] = []

        def factory(*, name: str, row: type[Any]) -> StubLedger[Any]:
            stub = StubLedger(name=name, row=row)
            created.append(stub)
            return stub

        for attribute in WiredStubLedgers._PATCHED_NAMES:
            if hasattr(module, attribute):
                monkeypatch.setattr(module, attribute, factory)

        return created
