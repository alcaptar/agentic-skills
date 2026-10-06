from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.exceptions import UnreadableProvenanceError
from slice_runner.domain.provenance import Provenance
from slice_runner.infrastructure.direct_url_payload import DirectUrlPayload
from slice_runner.infrastructure.uv_tool_installation import UvToolInstallation

if TYPE_CHECKING:
    from pathlib import Path


class UvProgramOrigin(Provenance):
    TOOL: ClassVar[str] = UvToolInstallation.TOOL
    VARIABLE: ClassVar[str] = UvToolInstallation.VARIABLE

    def checkout(self) -> Path:
        direct_url = UvToolInstallation().direct_url_file()

        return DirectUrlPayload.from_dict(self._decoded(direct_url)).to_domain()

    @staticmethod
    def _decoded(path: Path) -> dict[str, object]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise UnreadableProvenanceError(f"{path} is not valid JSON: {error}") from error
        if not isinstance(data, dict):
            raise UnreadableProvenanceError(f"{path} has to be an object, not {type(data).__name__}")

        return data
