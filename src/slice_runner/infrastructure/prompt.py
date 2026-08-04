from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar


class AgentPrompt:
    JUDGE: ClassVar[Path] = Path(__file__).resolve().parents[3] / "agents" / "slice-verifier.md"

    _LEADING_CONFIG_HEADER: ClassVar[re.Pattern[str]] = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)

    @classmethod
    def read(cls, path: Path) -> str:
        return cls._LEADING_CONFIG_HEADER.sub("", path.read_text(encoding="utf-8")).strip()
