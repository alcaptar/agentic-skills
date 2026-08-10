from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.step import Step
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.conversation_tool_use_recorder import ConversationToolUseRecorder
from slice_runner.infrastructure.local_conversation_log import LocalConversationLog
from slice_runner.infrastructure.local_tool_use_log import LocalToolUseLog
from slice_runner.tests.mothers.conversation_transcript_mother import ConversationTranscriptMother

if TYPE_CHECKING:
    from pathlib import Path

_REPO = "/Users/someone/repos/the-slice"
_SLICE_ID = "slice-05"


class WrittenToolUses:
    LEDGER: tuple[str, ...] = ("slice-runner", "trace", "tool-uses.jsonl")

    @classmethod
    def records_under(cls, root: Path) -> list[dict[str, object]]:
        ledger = root.joinpath(*cls.LEDGER)
        if not ledger.exists():
            return []

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


class WithTheToolUseLogOutOfTheRealHome:
    @pytest.fixture(autouse=True)
    def roots(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))


class TestARecordedConversation(WithTheToolUseLogOutOfTheRealHome):
    def test_every_tool_use_of_the_conversation_lands_in_the_log_labelled_with_the_slice_step_and_session(
        self, tmp_path: Path
    ) -> None:
        ConversationTranscriptMother.written_under(tmp_path, repo=_REPO)
        recorder = ConversationToolUseRecorder(conversations=LocalConversationLog(), tool_use_log=LocalToolUseLog())

        recorder.record_after(
            slice_id=_SLICE_ID, step=Step.IMPLEMENT, session=ConversationTranscriptMother.SESSION, repo=_REPO
        )

        assert WrittenToolUses.records_under(tmp_path) == [
            {
                "slice_id": _SLICE_ID,
                "step": "implement",
                "session": ConversationTranscriptMother.SESSION,
                "uses": [
                    {"turn": 2, "tool": "Bash"},
                    {"turn": 4, "tool": "Bash"},
                ],
            }
        ]


class TestATranscriptThatCannotBeRead(WithTheToolUseLogOutOfTheRealHome):
    def test_a_session_never_recorded_leaves_the_run_going_instead_of_raising(self, tmp_path: Path) -> None:
        recorder = ConversationToolUseRecorder(conversations=LocalConversationLog(), tool_use_log=LocalToolUseLog())

        recorder.record_after(slice_id=_SLICE_ID, step=Step.IMPLEMENT, session="never-recorded", repo=_REPO)

        assert WrittenToolUses.records_under(tmp_path) == []

    def test_a_corrupted_transcript_leaves_the_run_going_instead_of_raising(self, tmp_path: Path) -> None:
        session = "broken-session"
        encoded = _REPO.rstrip("/").replace("/", "-")
        destination = tmp_path / "projects" / encoded / f"{session}.jsonl"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("not json at all\n", encoding="utf-8")
        recorder = ConversationToolUseRecorder(conversations=LocalConversationLog(), tool_use_log=LocalToolUseLog())

        recorder.record_after(slice_id=_SLICE_ID, step=Step.IMPLEMENT, session=session, repo=_REPO)

        assert WrittenToolUses.records_under(tmp_path) == []
