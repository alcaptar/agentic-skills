from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from slice_runner.domain.skill_library import SkillLibrary


class LocalSkillLibrary(SkillLibrary):
    CONFIG_VARIABLE: ClassVar[str] = "CLAUDE_CONFIG_DIR"
    DEFAULT_CONFIG: ClassVar[str] = "~/.claude"
    TREES: ClassVar[tuple[str, ...]] = ("skills", "plugins")

    def directories(self) -> tuple[Path, ...]:
        root = self._configured_root()

        return tuple(tree for tree in (root / name for name in self.TREES) if tree.is_dir())

    def _configured_root(self) -> Path:
        return Path(os.environ.get(self.CONFIG_VARIABLE) or self.DEFAULT_CONFIG).expanduser()
