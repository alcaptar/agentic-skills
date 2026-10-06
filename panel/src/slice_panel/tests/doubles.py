from __future__ import annotations

from typing import TYPE_CHECKING

from slice_panel.domain.follow_source import FollowSource
from slice_panel.infrastructure.process_launcher import ProcessLauncher

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping, Sequence
    from pathlib import Path

    from slice_panel.domain.follow_ended import FollowEnded
    from slice_panel.domain.follow_line import FollowLine
    from slice_panel.infrastructure.process_outcome import ProcessOutcome


class ScriptedFollowSource(FollowSource):
    def __init__(self, *, lines: Sequence[FollowLine], ended: FollowEnded | None = None) -> None:
        self._lines = lines
        self._ended = ended

    async def events(self) -> AsyncIterator[FollowLine | FollowEnded]:
        for line in self._lines:
            yield line
        if self._ended is not None:
            yield self._ended


class RecordingLauncher(ProcessLauncher):
    def __init__(self, answers: Mapping[tuple[str, ...], ProcessOutcome | BaseException] | None = None) -> None:
        self._answers = dict(answers or {})
        self.calls: list[tuple[str, ...]] = []

    async def ran(self, argv: Sequence[str], *, cwd: Path | None = None) -> ProcessOutcome:
        key = tuple(argv)
        self.calls.append(key)
        if key not in self._answers:
            raise AssertionError(f"nobody wrote an answer for {key}")
        answer = self._answers[key]
        if isinstance(answer, BaseException):
            raise answer

        return answer

    def calls_to(self, *prefix: str) -> list[tuple[str, ...]]:
        return [call for call in self.calls if call[: len(prefix)] == prefix]
