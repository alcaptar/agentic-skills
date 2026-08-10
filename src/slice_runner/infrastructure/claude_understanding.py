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
    from slice_runner.domain.call_spend_log import CallSpendLog
    from slice_runner.domain.call_trace import CallTrace
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.sub_issue import SubIssue
    from slice_runner.infrastructure.process import Process
    from slice_runner.infrastructure.tool_use_recorder import ToolUseRecorder
    from slice_runner.infrastructure.turn_log import TurnLog


class ClaudeUnderstanding(UnderstandingWriter):
    def __init__(
        self,
        *,
        process: Process,
        trace: CallTrace,
        turns: TurnLog,
        spend_log: CallSpendLog,
        tool_uses: ToolUseRecorder,
    ) -> None:
        self._process = process
        self._trace = trace
        self._turns = turns
        self._spend_log = spend_log
        self._tool_uses = tool_uses

    def write(
        self, *, subissue: SubIssue, parent: ParentIssue, repo: str, worktree: str, alignment: Alignment
    ) -> Understanding:
        invocation = UnderstandingInvocation(
            subissue=subissue, parent=parent, repo=repo, worktree=worktree, alignment=alignment
        )
        watch = HarnessTurnWatch(turns=self._turns, slice_id=subissue.slice_id, step=Step.UNDERSTAND)
        output = self._process.run(invocation.argv, stdin=invocation.text, cwd=invocation.cwd, on_line=watch)
        envelope = HarnessOutput.from_process(output)
        self._trace.record(HarnessCall(slice_id=subissue.slice_id, step=Step.UNDERSTAND, session=envelope.session_id))
        spend = envelope.to_domain()
        self._spend_log.record(HarnessCallSpend(session=envelope.session_id, spend=spend))
        self._tool_uses.record_after(
            slice_id=subissue.slice_id, step=Step.UNDERSTAND, session=envelope.session_id, repo=repo
        )
        with envelope.measuring():
            text = self._usable_text(envelope)

        return Understanding(text=text, spend=spend)

    @staticmethod
    def _usable_text(envelope: HarnessOutput) -> str:
        report = UnderstandingReportPayload.from_dict(envelope.structured_output)
        text = report.understanding.strip()
        if not text:
            raise InvalidUnderstandingReportError("the harness returned only blank text as its understanding")

        return text
