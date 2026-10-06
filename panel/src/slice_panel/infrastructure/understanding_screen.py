from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

if TYPE_CHECKING:
    from textual.app import ComposeResult


class UnderstandingScreen(ModalScreen[None]):
    BINDINGS: ClassVar = [("escape", "close", "close"), ("e", "close", "close")]

    def __init__(self, text: str) -> None:
        super().__init__()
        self._text = text

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(self._text, id="understanding")

    def shown_text(self) -> str:
        return str(self.query_one("#understanding", Static).content)

    def action_close(self) -> None:
        self.dismiss(None)
