from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.verification import Verifier
from slice_runner.infrastructure.payloads import HarnessOutput, VerdictPayload

if TYPE_CHECKING:
    from slice_runner.domain.verdict import Verdict
    from slice_runner.domain.verification import VerificationRequest
    from slice_runner.infrastructure.process import Process


@dataclass(frozen=True, kw_only=True, slots=True)
class JudgeInvocation:
    EXECUTABLE: ClassVar[str] = "claude"
    TOOLS: ClassVar[tuple[str, ...]] = ("Read", "Grep", "Glob", "Skill")

    request: VerificationRequest

    @property
    def argv(self) -> list[str]:
        return [
            self.EXECUTABLE,
            "-p",
            "--output-format",
            "json",
            "--tools",
            ",".join(self.TOOLS),
            *self._grants_to_read,
            "--strict-mcp-config",
            "--json-schema",
            json.dumps(VerdictPayload.json_schema(), ensure_ascii=False),
        ]

    @property
    def prompt(self) -> str:
        diff = self.request.diff
        return "\n".join(
            [
                self.request.instructions,
                "",
                "## Datos del run",
                "",
                f"- ruta del repo: {self.request.repo}",
                f"- `slice.diff`: {diff.slice_diff}",
                f"- `files.txt`: {diff.files} ({diff.n_files} ficheros)",
            ]
        )

    @property
    def _grants_to_read(self) -> list[str]:
        directories = [str(self.request.diff.slice_diff.parent), self.request.repo]
        return [argument for directory in directories for argument in ("--add-dir", directory)]


class ClaudeVerifier(Verifier):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def verify(self, request: VerificationRequest) -> Verdict:
        invocation = JudgeInvocation(request=request)
        output = self._process.run(invocation.argv, stdin=invocation.prompt)
        envelope = HarnessOutput.from_process(output)
        return VerdictPayload.from_dict(envelope.structured_output).to_domain()
