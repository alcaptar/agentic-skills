from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.step import Step
from slice_runner.infrastructure.harness_invocation_runner import HarnessCallSubject, HarnessInvocationRunner
from slice_runner.infrastructure.harness_telemetry import HarnessTelemetry
from slice_runner.tests.doubles import (
    FixedInvocation,
    RecordedProcess,
    RecordedSpendLog,
    RecordedToolUseRecorder,
    RecordedTrace,
    RecordedTurnLog,
    StreamingProcess,
)
from slice_runner.tests.mothers.harness_call_spend_mother import HarnessCallSpendMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process

_SUBJECT = HarnessCallSubject(
    repo=HarnessCallSpendMother.REPO,
    issue=HarnessCallSpendMother.ISSUE,
    slice_id="slice-05",
    worktree="/repos/agentic-skills",
)


class Calling:
    @staticmethod
    def _runner(
        process: Process,
        *,
        trace: RecordedTrace | None = None,
        turns: RecordedTurnLog | None = None,
        spend_log: RecordedSpendLog | None = None,
        tool_uses: RecordedToolUseRecorder | None = None,
    ) -> HarnessInvocationRunner:
        return HarnessInvocationRunner(
            process=process,
            telemetry=HarnessTelemetry(
                trace=trace or RecordedTrace(),
                turns=turns or RecordedTurnLog(),
                spend_log=spend_log or RecordedSpendLog(),
                tool_uses=tool_uses or RecordedToolUseRecorder(),
            ),
        )


class TestTheInvocationTravelsToTheProcess(Calling):
    def test_the_argv_the_text_and_the_cwd_of_the_invocation_reach_the_process(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())
        runner = self._runner(process)
        invocation = FixedInvocation(argv=["claude", "--model", "opus"], text="the prompt", cwd="/repos/agentic-skills")

        runner.call(invocation, step=Step.VERIFY, subject=_SUBJECT)

        assert process.argv == invocation.argv
        assert process.stdin == invocation.text
        assert process.cwd == invocation.cwd


class TestWhatTheCallReturns(Calling):
    def test_the_envelope_returned_carries_the_structured_output_of_the_call(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())
        runner = self._runner(process)

        envelope = runner.call(FixedInvocation(), step=Step.VERIFY, subject=_SUBJECT)

        assert envelope.structured_output == HarnessEnvelopeMother.recorded()["structured_output"]


class TestTheTraceOfTheCall(Calling):
    def test_the_session_the_slice_and_the_step_of_the_call_are_written_down(self) -> None:
        trace = RecordedTrace()
        runner = self._runner(RecordedProcess(HarnessEnvelopeMother.recorded()), trace=trace)

        runner.call(FixedInvocation(), step=Step.VERIFY, subject=_SUBJECT)

        assert [(call.slice_id, call.step, call.session) for call in trace.calls] == [
            (_SUBJECT.slice_id, Step.VERIFY, HarnessEnvelopeMother.SESSION_OF_THE_JUDGE)
        ]

    def test_the_trace_carries_the_repo_and_the_issue_of_the_subject(self) -> None:
        trace = RecordedTrace()
        runner = self._runner(RecordedProcess(HarnessEnvelopeMother.recorded()), trace=trace)

        runner.call(FixedInvocation(), step=Step.VERIFY, subject=_SUBJECT)

        assert [(call.repo, call.issue) for call in trace.calls] == [(_SUBJECT.repo, _SUBJECT.issue)]


class TestTheSpendLogOfTheCall(Calling):
    def test_the_session_and_what_it_spent_are_written_down(self) -> None:
        spend_log = RecordedSpendLog()
        runner = self._runner(RecordedProcess(HarnessEnvelopeMother.recorded()), spend_log=spend_log)

        runner.call(FixedInvocation(), step=Step.VERIFY, subject=_SUBJECT)

        assert spend_log.calls == [HarnessCallSpendMother.of_the_judge()]


class TestTheToolUseRecordingOfTheCall(Calling):
    def test_the_recorder_is_asked_for_the_slice_step_session_and_worktree_of_the_call(self) -> None:
        tool_uses = RecordedToolUseRecorder()
        runner = self._runner(RecordedProcess(HarnessEnvelopeMother.recorded()), tool_uses=tool_uses)

        runner.call(FixedInvocation(), step=Step.VERIFY, subject=_SUBJECT)

        assert [(call.slice_id, call.step, call.session, call.worktree) for call in tool_uses.calls] == [
            (_SUBJECT.slice_id, Step.VERIFY, HarnessEnvelopeMother.SESSION_OF_THE_JUDGE, _SUBJECT.worktree)
        ]


class TestTheTurnsObservedWhileTheCallIsInFlight(Calling):
    def test_every_tool_use_of_a_real_streamed_call_is_observed_labelled_with_the_step_it_was_called_with(self) -> None:
        turns = RecordedTurnLog()
        runner = self._runner(StreamingProcess(HarnessEnvelopeMother.streamed()), turns=turns)

        runner.call(FixedInvocation(), step=Step.IMPLEMENT, subject=_SUBJECT)

        assert [(turn.slice_id, turn.step, turn.number, turn.tool, turn.target) for turn in turns.turns] == [
            (_SUBJECT.slice_id, Step.IMPLEMENT, 1, "Write", "/private/tmp/stream-capture2/repo/hello.py"),
            (_SUBJECT.slice_id, Step.IMPLEMENT, 2, "StructuredOutput", None),
        ]


class TestTheStepNeverStaysFixedInsideTheCommonPiece(Calling):
    def test_two_calls_with_different_steps_each_produce_a_trace_carrying_its_own_step(self) -> None:
        trace = RecordedTrace()
        runner = self._runner(RecordedProcess(HarnessEnvelopeMother.recorded()), trace=trace)

        runner.call(FixedInvocation(), step=Step.VERIFY, subject=_SUBJECT)
        runner.call(FixedInvocation(), step=Step.IMPLEMENT, subject=_SUBJECT)

        assert [call.step for call in trace.calls] == [Step.VERIFY, Step.IMPLEMENT]
