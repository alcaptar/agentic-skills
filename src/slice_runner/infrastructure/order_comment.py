from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.order import Order
from slice_runner.infrastructure.automation_mark import AutomationMark

if TYPE_CHECKING:
    from collections.abc import Iterator


class OrderComment:
    REOPENING_MARKER: ClassVar[str] = "<!-- slice-runner:reabierta -->"

    @classmethod
    def rendered(cls, order: Order, text: str) -> str:
        return "\n\n".join([cls._statement(order, text), *cls._markers_of(order), AutomationMark.TEXT])

    @classmethod
    def is_a_reopening(cls, body: str) -> bool:
        return cls.REOPENING_MARKER in body

    @classmethod
    def _markers_of(cls, order: Order) -> Iterator[str]:
        if order is Order.RETRY:
            yield cls.REOPENING_MARKER

    @staticmethod
    def _statement(order: Order, text: str) -> str:
        if not text:
            return f"Orden `{order}` dada con `slice-runner`."

        return f"Orden `{order}` dada con `slice-runner`, con este texto:\n\n{text}"
