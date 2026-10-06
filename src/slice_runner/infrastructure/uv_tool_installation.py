from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from slice_runner.domain.exceptions import UnreadableProvenanceError


class UvToolInstallation:
    TOOL: ClassVar[str] = "agentic-skills"
    DISTRIBUTION: ClassVar[str] = "agentic_skills"
    PACKAGE: ClassVar[str] = "slice_runner"
    VARIABLE: ClassVar[str] = "UV_TOOL_DIR"
    DEFAULT: ClassVar[str] = "~/.local/share/uv/tools"

    def direct_url_file(self) -> Path:
        pattern = f"lib/python*/site-packages/{self.DISTRIBUTION}-*.dist-info/direct_url.json"
        matches = sorted((self._root() / self.TOOL).glob(pattern))
        if not matches:
            raise UnreadableProvenanceError(f"no direct_url.json found under {self._root() / self.TOOL}")

        return matches[0]

    def installed_package(self) -> Path:
        return self.direct_url_file().parent.parent / self.PACKAGE

    def _root(self) -> Path:
        return Path(os.environ.get(self.VARIABLE) or self.DEFAULT).expanduser()
