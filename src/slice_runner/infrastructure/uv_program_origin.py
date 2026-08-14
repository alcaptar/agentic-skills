from __future__ import annotations

import json
import os
from pathlib import Path
from typing import ClassVar

from slice_runner.domain.exceptions import UnreadableProvenanceError
from slice_runner.domain.provenance import Provenance
from slice_runner.infrastructure.direct_url_payload import DirectUrlPayload


class UvProgramOrigin(Provenance):
    TOOL: ClassVar[str] = "agentic-skills"
    DISTRIBUTION: ClassVar[str] = "agentic_skills"
    VARIABLE: ClassVar[str] = "UV_TOOL_DIR"
    DEFAULT: ClassVar[str] = "~/.local/share/uv/tools"

    def checkout(self) -> Path:
        direct_url = self._direct_url_file()
        if direct_url is None:
            raise UnreadableProvenanceError(f"no direct_url.json found under {self._root() / self.TOOL}")

        return DirectUrlPayload.from_dict(self._decoded(direct_url)).to_domain()

    def _root(self) -> Path:
        return Path(os.environ.get(self.VARIABLE) or self.DEFAULT).expanduser()

    def _direct_url_file(self) -> Path | None:
        pattern = f"lib/python*/site-packages/{self.DISTRIBUTION}-*.dist-info/direct_url.json"
        matches = sorted((self._root() / self.TOOL).glob(pattern))

        return matches[0] if matches else None

    @staticmethod
    def _decoded(path: Path) -> dict[str, object]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise UnreadableProvenanceError(f"{path} is not valid JSON: {error}") from error
        if not isinstance(data, dict):
            raise UnreadableProvenanceError(f"{path} has to be an object, not {type(data).__name__}")

        return data
