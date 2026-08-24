from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.alignment import Alignment
from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.infrastructure.claude_understanding import ClaudeUnderstanding
from slice_runner.infrastructure.harness_invocation_runner import HarnessInvocationRunner
from slice_runner.infrastructure.harness_telemetry import HarnessTelemetry
from slice_runner.tests.doubles import (
    RecordedProcess,
    RecordedSourceReader,
    RecordedSpendLog,
    RecordedToolUseRecorder,
    RecordedTrace,
    RecordedTurnLog,
)
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
        alignment: Alignment | None = None,
        trace: RecordedTrace | None = None,
        tool_uses: RecordedToolUseRecorder | None = None,
    ) -> Understanding:
        calls = HarnessInvocationRunner(
            process=process,
            telemetry=HarnessTelemetry(
                trace=trace or RecordedTrace(),
                turns=RecordedTurnLog(),
                spend_log=RecordedSpendLog(),
                tool_uses=tool_uses or RecordedToolUseRecorder(),
            ),
        )

        return ClaudeUnderstanding(calls=calls, reader=RecordedSourceReader()).write(
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


class TestTheCallSubjectComesFromItsOwnArguments:
    def test_the_trace_carries_the_calls_own_repo_issue_and_slice_id_and_not_a_crossed_field(self) -> None:
        trace = RecordedTrace()
        subissue = SubIssueMother.pending()

        Writing.understood(Writing.carrying(UnderstandingReportMother.valid()), trace=trace)

        recorded = trace.calls[0]
        assert (recorded.repo, recorded.issue, recorded.slice_id) == (
            UnderstandingInvocationMother.REPO,
            subissue.number,
            subissue.slice_id.canonical,
        )

    def test_the_tool_use_recording_carries_the_calls_own_worktree_and_slice_id(self) -> None:
        tool_uses = RecordedToolUseRecorder()
        subissue = SubIssueMother.pending()

        Writing.understood(Writing.carrying(UnderstandingReportMother.valid()), tool_uses=tool_uses)

        recorded = tool_uses.calls[0]
        assert (recorded.worktree, recorded.slice_id) == (
            UnderstandingInvocationMother.WORKTREE,
            subissue.slice_id.canonical,
        )


class TestTheUnderstandingOfARecordedCall:
    def test_the_report_is_published_exactly_as_the_harness_wrote_it_instead_of_being_recomposed(self) -> None:
        understanding = Writing.understood(Writing.carrying(UnderstandingReportMother.valid()))

        assert understanding.text == UnderstandingReportMother.REPORT

    def test_the_markdown_of_the_report_survives_because_the_program_never_takes_it_apart(self) -> None:
        understanding = Writing.understood(Writing.carrying(UnderstandingReportMother.valid()))

        assert "\n- infrastructure/understanding_report_payload.py:" in understanding.text

    def test_surrounding_blank_space_is_trimmed_because_it_is_not_part_of_what_was_understood(self) -> None:
        padded: dict[str, object] = {"report": f"  \n{UnderstandingReportMother.REPORT}  \n\n"}

        understanding = Writing.understood(Writing.carrying(padded))

        assert understanding.text == UnderstandingReportMother.REPORT

    def test_what_the_harness_spent_on_the_call_travels_with_the_understanding(self) -> None:
        understanding = Writing.understood(Writing.carrying(UnderstandingReportMother.valid()))

        assert understanding.spend == HarnessSpendMother.of_the_implementer_call()


class TestWhatTheCallIsAllowedToReturn:
    def test_a_report_missing_its_only_field_is_rejected_instead_of_passing_through_as_free_text(self) -> None:
        process = Writing.carrying(UnderstandingReportMother.without("report"))

        with pytest.raises(InvalidUnderstandingReportError, match="report"):
            Writing.understood(process)

    def test_a_blank_report_is_rejected_because_it_is_not_usable_as_a_gate(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError):
            Writing.understood(Writing.carrying(UnderstandingReportMother.blank()))

    def test_a_rejected_call_still_reports_what_it_spent_so_the_budget_still_sees_it(self) -> None:
        blank = UnderstandingReportMother.blank()

        with pytest.raises(InvalidUnderstandingReportError) as rejection:
            Writing.understood(Writing.carrying(blank))

        assert rejection.value.spend == HarnessSpendMother.of_the_implementer_call()
