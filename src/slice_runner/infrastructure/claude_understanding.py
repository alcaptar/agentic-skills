from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.call_spend_log import HarnessCallSpend
from slice_runner.domain.call_trace import HarnessCall
from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.domain.step import Step
from slice_runner.domain.understanding import Understanding
from slice_runner.domain.understanding_writer import UnderstandingWriter
from slice_runner.infrastructure.harness_output import HarnessOutput
from slice_runner.infrastructure.harness_turn_watch import HarnessTurnWatch
from slice_runner.infrastructure.understanding_invocation import UnderstandingInvocation
from slice_runner.infrastructure.understanding_report_payload import UnderstandingReportPayload

if TYPE_CHECKING:
    from slice_runner.domain.alignment import Alignment
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.source_reader import SourceReader
    from slice_runner.domain.sub_issue import SubIssue
    from slice_runner.infrastructure.harness_telemetry import HarnessTelemetry
    from slice_runner.infrastructure.process import Process


class ClaudeUnderstanding(UnderstandingWriter):
    def __init__(self, *, process: Process, telemetry: HarnessTelemetry, reader: SourceReader) -> None:
        self._process = process
        self._telemetry = telemetry
        self._reader = reader

    def write(
        self, *, subissue: SubIssue, parent: ParentIssue, repo: str, worktree: str, alignment: Alignment
    ) -> Understanding:
        invocation = UnderstandingInvocation(
            subissue=subissue,
            parent=parent,
            repo=repo,
            worktree=worktree,
            alignment=alignment,
            reader=self._reader,
        )
        watch = HarnessTurnWatch(turns=self._telemetry.turns, slice_id=subissue.slice_id, step=Step.UNDERSTAND)
        output = self._process.run(invocation.argv, stdin=invocation.text, cwd=invocation.cwd, on_line=watch)
        envelope = HarnessOutput.from_process(output)
        self._telemetry.trace.record(
            HarnessCall(
                repo=repo,
                issue=subissue.number,
                slice_id=subissue.slice_id,
                step=Step.UNDERSTAND,
                session=envelope.session_id,
            )
        )
        spend = envelope.to_domain()
        self._telemetry.spend_log.record(
            HarnessCallSpend(repo=repo, issue=subissue.number, session=envelope.session_id, spend=spend)
        )
        self._telemetry.tool_uses.record_after(
            slice_id=subissue.slice_id, step=Step.UNDERSTAND, session=envelope.session_id, repo=repo
        )
        with envelope.measuring():
            text = self._usable_text(envelope)

        return Understanding(text=text, spend=spend)

    @classmethod
    def _usable_text(cls, envelope: HarnessOutput) -> str:
        report = UnderstandingReportPayload.from_dict(envelope.structured_output)
        summary = report.summary.strip()
        pieces = [(piece.signature.strip(), piece.does.strip(), piece.reason.strip()) for piece in report.plan]
        if not summary or any(not signature or not does or not reason for signature, does, reason in pieces):
            raise InvalidUnderstandingReportError("the harness returned only blank text as its understanding")

        return "\n\n".join([f"## Resumen\n{summary}", f"## Plan\n{cls._fenced(pieces)}"])

    @staticmethod
    def _fenced(pieces: list[tuple[str, str, str]]) -> str:
        drawn = "\n\n".join(f"{signature}\n    {does}\n    motivo: {reason}" for signature, does, reason in pieces)

        return f"```\n{drawn}\n```"
