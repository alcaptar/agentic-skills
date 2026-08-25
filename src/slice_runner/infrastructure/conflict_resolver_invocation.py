from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.cited_sources import CitedSources
from slice_runner.infrastructure.conflict_resolver_brief import ConflictResolverBrief
from slice_runner.infrastructure.counted_lines import CountedLines
from slice_runner.infrastructure.harness_invocation_runner import HarnessInvocation
from slice_runner.infrastructure.resolution_report_payload import ResolutionReportPayload

if TYPE_CHECKING:
    from slice_runner.domain.merge_conflict import MergeConflict
    from slice_runner.domain.source_reader import SourceReader


@dataclass(frozen=True, kw_only=True, slots=True)
class ConflictResolverInvocation(HarnessInvocation):
    EXECUTABLE: ClassVar[str] = "claude"
    MODEL: ClassVar[str] = "sonnet"

    conflict: MergeConflict
    reader: SourceReader

    @property
    def cwd(self) -> str:
        return self.conflict.worktree

    @property
    def argv(self) -> list[str]:
        return [
            self.EXECUTABLE,
            "-p",
            "--model",
            self.MODEL,
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
            "--tools",
            ",".join(ConflictResolverBrief.TOOLS),
            "--strict-mcp-config",
            "--setting-sources",
            "user",
            "--json-schema",
            json.dumps(ResolutionReportPayload.json_schema(), ensure_ascii=False),
        ]

    @property
    def text(self) -> str:
        return "\n".join([ConflictResolverBrief.TEXT, "", self._conflict_data])

    @property
    def _conflict_data(self) -> str:
        conflict = self.conflict

        return "\n".join(
            [
                "## Datos del conflicto",
                "",
                f"- issue: #{conflict.issue}",
                f"- slice: {conflict.slice_id}",
                f"- repo: {conflict.repo}",
                f"- ruta del repo: {conflict.worktree}",
                f"- rama: {conflict.branch}",
                f"- base: {conflict.base}",
                *CountedLines.of("ficheros en conflicto", conflict.conflicted_paths),
                *CitedSources.of(
                    "fuentes de convencion",
                    reader=self.reader,
                    worktree=conflict.worktree,
                    sources=conflict.sources,
                ),
            ]
        )
