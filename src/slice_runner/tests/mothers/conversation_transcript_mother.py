from __future__ import annotations

from pathlib import Path
from typing import ClassVar


class ConversationTranscriptMother:
    SESSION: ClassVar[str] = "779e530f-c285-495c-bbdc-f2896f81fe25"

    _RECORDED: ClassVar[Path] = Path(__file__).resolve().parents[1] / "payloads" / "conversation-turns.jsonl"

    @classmethod
    def written_under(cls, root: Path, *, repo: str) -> None:
        encoded = repo.rstrip("/").replace("/", "-")
        destination = root / "projects" / encoded / f"{cls.SESSION}.jsonl"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(cls._RECORDED.read_text(encoding="utf-8"), encoding="utf-8")
