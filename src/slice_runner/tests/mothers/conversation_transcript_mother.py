from __future__ import annotations

from pathlib import Path
from typing import ClassVar


class ConversationTranscriptMother:
    SESSION: ClassVar[str] = "779e530f-c285-495c-bbdc-f2896f81fe25"
    REJECTED_STRUCTURED_OUTPUT: ClassVar[str] = "conversation-with-a-rejected-structured-output"
    WORKTREE: ClassVar[str] = "/repos/mo.ntc.control.api/.claude/worktrees/the-slice"
    PROJECT_DIRECTORY: ClassVar[str] = "-repos-mo-ntc-control-api--claude-worktrees-the-slice"

    _PAYLOADS: ClassVar[Path] = Path(__file__).resolve().parents[1] / "payloads"

    @classmethod
    def written_under(cls, root: Path, *, recorded: str = "conversation-turns") -> None:
        cls.destination_of(root, session=cls.SESSION).write_text(
            (cls._PAYLOADS / f"{recorded}.jsonl").read_text(encoding="utf-8"), encoding="utf-8"
        )

    @classmethod
    def destination_of(cls, root: Path, *, session: str) -> Path:
        destination = root / "projects" / cls.PROJECT_DIRECTORY / f"{session}.jsonl"
        destination.parent.mkdir(parents=True, exist_ok=True)

        return destination
