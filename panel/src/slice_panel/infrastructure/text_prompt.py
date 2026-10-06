from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label

if TYPE_CHECKING:
    from textual.app import ComposeResult


class TextPrompt(ModalScreen[str | None]):
    BINDINGS: ClassVar = [("escape", "cancel", "cancel")]
    DEFAULT_CSS: ClassVar[str] = """
    TextPrompt { align: center middle; }
    TextPrompt Vertical { width: 70%; height: auto; border: round white; background: $surface; padding: 1; }
    """

    def __init__(self, question: str) -> None:
        super().__init__()
        self._question = question

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._question)
            yield Input(id="answer")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def action_cancel(self) -> None:
        self.dismiss(None)
