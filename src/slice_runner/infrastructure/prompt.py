from __future__ import annotations

import re
from pathlib import Path

JUDGE_PROMPT_PATH = Path(__file__).resolve().parents[3] / "agents" / "slice-verifier.md"

_LEADING_CONFIG_HEADER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def read_agent_prompt(path: Path) -> str:
    return _LEADING_CONFIG_HEADER.sub("", path.read_text(encoding="utf-8")).strip()
