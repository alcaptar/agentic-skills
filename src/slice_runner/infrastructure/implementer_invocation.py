from __future__ import annotations

import json
from dataclasses import dataclass
from typing import ClassVar

from slice_runner.infrastructure.report_payload import ImplementationReportPayload
from slice_runner.infrastructure.slice_implementer_brief import SliceImplementerBrief


@dataclass(frozen=True, kw_only=True, slots=True)
class ImplementerInvocation:
    EXECUTABLE: ClassVar[str] = "claude"

    repo: str

    @property
    def cwd(self) -> str:
        return self.repo

    @property
    def argv(self) -> list[str]:
        return [
            self.EXECUTABLE,
            "-p",
            "--output-format",
            "json",
            "--permission-mode",
            "bypassPermissions",
            "--tools",
            ",".join(SliceImplementerBrief.TOOLS),
            "--strict-mcp-config",
            "--json-schema",
            json.dumps(ImplementationReportPayload.json_schema(), ensure_ascii=False),
        ]

    @property
    def text(self) -> str:
        return SliceImplementerBrief.TEXT
