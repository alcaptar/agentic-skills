from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.alignment import Alignment
from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.domain.step import Step
from slice_runner.infrastructure.claude_understanding import ClaudeUnderstanding
from slice_runner.infrastructure.harness_telemetry import HarnessTelemetry
from slice_runner.tests.doubles import (
    RecordedProcess,
    RecordedSourceReader,
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
from slice_runner.tests.mothers.understanding_report_mother import UnderstandingReportMother

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
            telemetry=HarnessTelemetry(
                trace=trace or RecordedTrace(),
                turns=turns or RecordedTurnLog(),
                spend_log=spend_log or RecordedSpendLog(),
                tool_uses=tool_uses or RecordedToolUseRecorder(),
            ),
            reader=RecordedSourceReader(),
        ).write(
            subissue=SubIssueMother.pending(),
            parent=ParentIssueMother.with_sources_and_controls(),
            repo=UnderstandingInvocationMother.REPO,
            worktree=UnderstandingInvocationMother.WORKTREE,
            alignment=alignment or Alignment(),
        )

    @staticmethod
    def carrying(report: dict[str, object]) -> RecordedProcess:
        return RecordedProcess(HarnessEnvelopeMother.carrying(report, recorded=_RECORDED))


class TestWhereTheProcessRuns:
    def test_the_worktree_becomes_the_working_directory_of_the_process_and_not_the_gh_repo_slug(self) -> None:
        process = Writing.carrying(UnderstandingReportMother.valid())

        Writing.understood(process)

        assert process.cwd == UnderstandingInvocationMother.WORKTREE

    def test_the_harness_is_invoked_exactly_once_because_a_retry_is_a_decision_of_whoever_orchestrates(self) -> None:
        process = Writing.carrying(UnderstandingReportMother.valid())

        Writing.understood(process)

        assert process.calls == 1

    def test_a_correction_travels_on_standard_input_so_the_writer_rewrites_around_it(self) -> None:
        process = Writing.carrying(UnderstandingReportMother.valid())

        Writing.understood(process, alignment=Alignment(correction="la senal no esta exenta, hay que medirla"))

        assert "la senal no esta exenta, hay que medirla" in process.stdin


class TestTheUnderstandingOfARecordedCall:
    def test_the_summary_and_the_plan_arrive_composed_into_one_text_with_fixed_sections(self) -> None:
        understanding = Writing.understood(Writing.carrying(UnderstandingReportMother.valid()))

        assert understanding.text == (
            "## Resumen\n"
            f"{UnderstandingReportMother.SUMMARY}\n"
            "\n"
            "## Plan\n"
            "```\n"
            f"{UnderstandingReportMother.SIGNATURE}\n"
            f"    {UnderstandingReportMother.DOES}\n"
            f"    motivo: {UnderstandingReportMother.REASON}\n"
            "\n"
            f"{UnderstandingReportMother.SECOND_SIGNATURE}\n"
            f"    {UnderstandingReportMother.SECOND_DOES}\n"
            f"    motivo: {UnderstandingReportMother.SECOND_REASON}\n"
            "```"
        )

    def test_the_plan_is_fenced_by_the_program_so_markdown_cannot_eat_the_indentation_of_the_shape(self) -> None:
        understanding = Writing.understood(Writing.carrying(UnderstandingReportMother.with_pieces(3)))

        fenced = understanding.text.split("## Plan\n", maxsplit=1)[1]

        assert fenced.startswith("```\n")
        assert fenced.endswith("\n```")
        assert fenced.count(f"    {UnderstandingReportMother.DOES}") == 3

    def test_two_understandings_with_different_content_still_produce_the_same_section_structure(self) -> None:
        first = Writing.understood(Writing.carrying(UnderstandingReportMother.valid()))
        second = Writing.understood(
            Writing.carrying(
                UnderstandingReportMother.valid() | {"summary": f"otro resumen: {UnderstandingReportMother.SUMMARY}"}
            )
        )

        headings = ("## Resumen", "## Plan")
        assert [heading for heading in headings if heading in first.text] == list(headings)
        assert [heading for heading in headings if heading in second.text] == list(headings)
        assert first.text != second.text

    def test_surrounding_blank_space_in_each_field_is_trimmed_because_it_is_not_part_of_what_was_understood(
        self,
    ) -> None:
        padded = UnderstandingReportMother.valid() | {
            "summary": f"  {UnderstandingReportMother.SUMMARY}  \n",
            "plan": [
                {
                    "signature": f"  {UnderstandingReportMother.SIGNATURE}  \n",
                    "does": f"  {UnderstandingReportMother.DOES}  \n",
                    "reason": f"  {UnderstandingReportMother.REASON}  \n",
                }
            ],
        }

        understanding = Writing.understood(Writing.carrying(padded))

        assert UnderstandingReportMother.SUMMARY in understanding.text
        assert understanding.text.endswith(f"motivo: {UnderstandingReportMother.REASON}\n```")

    def test_what_the_harness_spent_on_the_call_travels_with_the_understanding(self) -> None:
        understanding = Writing.understood(Writing.carrying(UnderstandingReportMother.valid()))

        assert understanding.spend == HarnessSpendMother.of_the_implementer_call()


class TestWhatTheCallIsAllowedToReturn:
    def test_a_report_missing_the_plan_is_rejected_instead_of_passing_through_as_free_text(self) -> None:
        process = Writing.carrying(UnderstandingReportMother.without("plan"))

        with pytest.raises(InvalidUnderstandingReportError, match="plan"):
            Writing.understood(process)

    def test_a_piece_missing_its_reason_is_rejected_instead_of_passing_through_as_prose_in_does(
        self,
    ) -> None:
        process = Writing.carrying(UnderstandingReportMother.with_a_piece_missing_its_reason())

        with pytest.raises(InvalidUnderstandingReportError, match="reason"):
            Writing.understood(process)

    def test_blank_summary_is_rejected_because_it_is_not_usable_as_a_gate(self) -> None:
        blank = UnderstandingReportMother.valid() | {"summary": " " * 200}

        with pytest.raises(InvalidUnderstandingReportError):
            Writing.understood(Writing.carrying(blank))

    def test_a_piece_with_a_blank_does_is_rejected_because_it_is_not_usable_as_a_gate(self) -> None:
        blank = UnderstandingReportMother.valid() | {
            "plan": [{"signature": " " * 40, "does": " " * 40, "reason": " " * 40}]
        }

        with pytest.raises(InvalidUnderstandingReportError):
            Writing.understood(Writing.carrying(blank))

    def test_a_piece_with_a_blank_reason_is_rejected_because_it_is_not_usable_as_a_gate(self) -> None:
        blank = UnderstandingReportMother.valid() | {
            "plan": [
                {
                    "signature": UnderstandingReportMother.SIGNATURE,
                    "does": UnderstandingReportMother.DOES,
                    "reason": " " * 40,
                }
            ]
        }

        with pytest.raises(InvalidUnderstandingReportError):
            Writing.understood(Writing.carrying(blank))

    def test_a_rejected_call_still_reports_what_it_spent_so_the_budget_still_sees_it(self) -> None:
        blank = UnderstandingReportMother.valid() | {"summary": "   "}

        with pytest.raises(InvalidUnderstandingReportError) as rejection:
            Writing.understood(Writing.carrying(blank))

        assert rejection.value.spend == HarnessSpendMother.of_the_implementer_call()


class TestWhereTheConversationCanBeFound:
    def test_the_session_the_call_ran_under_is_written_down_under_the_slice_and_the_understand_step(self) -> None:
        trace = RecordedTrace()

        Writing.understood(Writing.carrying(UnderstandingReportMother.valid()), trace=trace)

        assert [(call.slice_id, call.step, call.session) for call in trace.calls] == [
            (
                SubIssueMother.pending().slice_id.canonical,
                Step.UNDERSTAND,
                HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER,
            )
        ]

    def test_a_call_whose_report_is_rejected_is_traced_too_because_that_conversation_is_the_one_to_read(self) -> None:
        trace = RecordedTrace()
        blank = UnderstandingReportMother.valid() | {"summary": "   "}

        with pytest.raises(InvalidUnderstandingReportError):
            Writing.understood(Writing.carrying(blank), trace=trace)

        assert [call.session for call in trace.calls] == [HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER]


class TestTheSpendLogOfTheCall:
    def test_the_session_and_what_it_spent_are_written_down(self) -> None:
        spend_log = RecordedSpendLog()

        Writing.understood(Writing.carrying(UnderstandingReportMother.valid()), spend_log=spend_log)

        assert spend_log.calls == [HarnessCallSpendMother.of_the_implementer()]

    def test_a_call_whose_report_is_rejected_still_leaves_its_spend_behind(self) -> None:
        spend_log = RecordedSpendLog()
        blank = UnderstandingReportMother.valid() | {"summary": "   "}

        with pytest.raises(InvalidUnderstandingReportError):
            Writing.understood(Writing.carrying(blank), spend_log=spend_log)

        assert [call.session for call in spend_log.calls] == [HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER]


class TestTheToolUseRecordingOfTheCall:
    def test_the_recorder_is_asked_for_the_slice_step_session_and_repo_of_the_call(self) -> None:
        tool_uses = RecordedToolUseRecorder()

        Writing.understood(Writing.carrying(UnderstandingReportMother.valid()), tool_uses=tool_uses)

        assert [(call.slice_id, call.step, call.session, call.repo) for call in tool_uses.calls] == [
            (
                SubIssueMother.pending().slice_id.canonical,
                Step.UNDERSTAND,
                HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER,
                UnderstandingInvocationMother.REPO,
            )
        ]

    def test_a_call_whose_report_is_rejected_is_recorded_too_because_that_conversation_is_the_one_to_read(
        self,
    ) -> None:
        tool_uses = RecordedToolUseRecorder()
        blank = UnderstandingReportMother.valid() | {"summary": "   "}

        with pytest.raises(InvalidUnderstandingReportError):
            Writing.understood(Writing.carrying(blank), tool_uses=tool_uses)

        assert [call.session for call in tool_uses.calls] == [HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER]


class TestTheTurnsObservedWhileTheCallIsInFlight:
    def test_every_tool_use_of_a_real_streamed_call_is_observed_labelled_with_the_understand_step(self) -> None:
        process = StreamingProcess(HarnessEnvelopeMother.streamed())
        turns = RecordedTurnLog()

        with pytest.raises(InvalidUnderstandingReportError):
            Writing.understood(process, turns=turns)

        assert [(turn.slice_id, turn.step, turn.number, turn.tool) for turn in turns.turns] == [
            (SubIssueMother.pending().slice_id.canonical, Step.UNDERSTAND, 1, "Write"),
            (SubIssueMother.pending().slice_id.canonical, Step.UNDERSTAND, 2, "StructuredOutput"),
        ]
