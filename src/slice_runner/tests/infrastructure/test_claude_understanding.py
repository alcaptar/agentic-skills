from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.alignment import Alignment
from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.domain.step import Step
from slice_runner.infrastructure.claude_understanding import ClaudeUnderstanding
from slice_runner.tests.doubles import (
    RecordedProcess,
    RecordedSpendLog,
    RecordedToolUseRecorder,
    RecordedTrace,
    RecordedTurnLog,
    StreamingProcess,
)
from slice_runner.tests.mothers.harness_call_spend_mother import HarnessCallSpendMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.understanding_invocation_mother import UnderstandingInvocationMother

if TYPE_CHECKING:
    from slice_runner.domain.understanding import Understanding
    from slice_runner.infrastructure.process import Process

_RECORDED = "implementer-two-paths"


class Writing:
    @staticmethod
    def understood(
        process: Process,
        *,
        trace: RecordedTrace | None = None,
        turns: RecordedTurnLog | None = None,
        spend_log: RecordedSpendLog | None = None,
        tool_uses: RecordedToolUseRecorder | None = None,
        alignment: Alignment | None = None,
    ) -> Understanding:
        return ClaudeUnderstanding(
            process=process,
            trace=trace or RecordedTrace(),
            turns=turns or RecordedTurnLog(),
            spend_log=spend_log or RecordedSpendLog(),
            tool_uses=tool_uses or RecordedToolUseRecorder(),
        ).write(
            subissue=SubIssueMother.pending(),
            parent=ParentIssueMother.with_sources_and_controls(),
            repo=UnderstandingInvocationMother.REPO,
            worktree=UnderstandingInvocationMother.WORKTREE,
            alignment=alignment or Alignment(),
        )

    @staticmethod
    def carrying(text: str) -> RecordedProcess:
        return RecordedProcess(HarnessEnvelopeMother.carrying({"understanding": text}, recorded=_RECORDED))


class TestWhereTheProcessRuns:
    def test_the_worktree_becomes_the_working_directory_of_the_process_and_not_the_gh_repo_slug(self) -> None:
        process = Writing.carrying("asi entiendo la slice")

        Writing.understood(process)

        assert process.cwd == UnderstandingInvocationMother.WORKTREE

    def test_a_correction_travels_on_standard_input_so_the_writer_rewrites_around_it(self) -> None:
        process = Writing.carrying("asi entiendo la slice, ya corregida")

        Writing.understood(process, alignment=Alignment(correction="la senal no esta exenta, hay que medirla"))

        assert "la senal no esta exenta, hay que medirla" in process.stdin


class TestTheUnderstandingOfARecordedCall:
    def test_the_text_the_harness_wrote_arrives_whole(self) -> None:
        understanding = Writing.understood(Writing.carrying("asi entiendo la slice y este es mi plan"))

        assert understanding.text == "asi entiendo la slice y este es mi plan"

    def test_surrounding_blank_space_is_trimmed_because_it_is_not_part_of_what_was_understood(self) -> None:
        understanding = Writing.understood(Writing.carrying("  asi entiendo la slice  \n"))

        assert understanding.text == "asi entiendo la slice"

    def test_what_the_harness_spent_on_the_call_travels_with_the_understanding(self) -> None:
        understanding = Writing.understood(Writing.carrying("asi entiendo la slice"))

        assert understanding.spend == HarnessSpendMother.of_the_implementer_call()


class TestWhatTheCallIsAllowedToReturn:
    def test_a_report_missing_the_only_field_it_may_carry_is_rejected_instead_of_defaulted(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.carrying({}, recorded=_RECORDED))

        with pytest.raises(InvalidUnderstandingReportError, match="understanding"):
            Writing.understood(process)

    def test_blank_text_is_rejected_because_it_is_not_usable_as_a_gate(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError):
            Writing.understood(Writing.carrying("   "))

    def test_a_rejected_call_still_reports_what_it_spent_so_the_budget_still_sees_it(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError) as rejection:
            Writing.understood(Writing.carrying("   "))

        assert rejection.value.spend == HarnessSpendMother.of_the_implementer_call()


class TestWhereTheConversationCanBeFound:
    def test_the_session_the_call_ran_under_is_written_down_under_the_slice_and_the_understand_step(self) -> None:
        trace = RecordedTrace()

        Writing.understood(Writing.carrying("asi entiendo la slice"), trace=trace)

        assert [(call.slice_id, call.step, call.session) for call in trace.calls] == [
            (SubIssueMother.pending().slice_id, Step.UNDERSTAND, HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER)
        ]

    def test_a_call_whose_report_is_rejected_is_traced_too_because_that_conversation_is_the_one_to_read(self) -> None:
        trace = RecordedTrace()

        with pytest.raises(InvalidUnderstandingReportError):
            Writing.understood(Writing.carrying("   "), trace=trace)

        assert [call.session for call in trace.calls] == [HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER]


class TestTheSpendLogOfTheCall:
    def test_the_session_and_what_it_spent_are_written_down(self) -> None:
        spend_log = RecordedSpendLog()

        Writing.understood(Writing.carrying("asi entiendo la slice"), spend_log=spend_log)

        assert spend_log.calls == [HarnessCallSpendMother.of_the_implementer()]

    def test_a_call_whose_report_is_rejected_still_leaves_its_spend_behind(self) -> None:
        spend_log = RecordedSpendLog()

        with pytest.raises(InvalidUnderstandingReportError):
            Writing.understood(Writing.carrying("   "), spend_log=spend_log)

        assert [call.session for call in spend_log.calls] == [HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER]


class TestTheToolUseRecordingOfTheCall:
    def test_the_recorder_is_asked_for_the_slice_step_session_and_repo_of_the_call(self) -> None:
        tool_uses = RecordedToolUseRecorder()

        Writing.understood(Writing.carrying("asi entiendo la slice"), tool_uses=tool_uses)

        assert [(call.slice_id, call.step, call.session, call.repo) for call in tool_uses.calls] == [
            (
                SubIssueMother.pending().slice_id,
                Step.UNDERSTAND,
                HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER,
                UnderstandingInvocationMother.REPO,
            )
        ]

    def test_a_call_whose_report_is_rejected_is_recorded_too_because_that_conversation_is_the_one_to_read(
        self,
    ) -> None:
        tool_uses = RecordedToolUseRecorder()

        with pytest.raises(InvalidUnderstandingReportError):
            Writing.understood(Writing.carrying("   "), tool_uses=tool_uses)

        assert [call.session for call in tool_uses.calls] == [HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER]


class TestTheTurnsObservedWhileTheCallIsInFlight:
    def test_every_tool_use_of_a_real_streamed_call_is_observed_labelled_with_the_understand_step(self) -> None:
        process = StreamingProcess(HarnessEnvelopeMother.streamed())
        turns = RecordedTurnLog()

        with pytest.raises(InvalidUnderstandingReportError):
            Writing.understood(process, turns=turns)

        assert [(turn.slice_id, turn.step, turn.number, turn.tool) for turn in turns.turns] == [
            (SubIssueMother.pending().slice_id, Step.UNDERSTAND, 1, "Write"),
            (SubIssueMother.pending().slice_id, Step.UNDERSTAND, 2, "StructuredOutput"),
        ]
