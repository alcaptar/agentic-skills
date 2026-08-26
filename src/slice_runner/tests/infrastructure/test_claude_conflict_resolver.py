from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import InvalidResolutionReportError, PermissionDeniedError
from slice_runner.domain.step import Step
from slice_runner.infrastructure.claude_conflict_resolver import ClaudeConflictResolver
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
from slice_runner.tests.mothers.merge_conflict_mother import MergeConflictMother
from slice_runner.tests.mothers.resolution_report_mother import ResolutionReportMother

if TYPE_CHECKING:
    from slice_runner.domain.conflict_resolution import ConflictResolution
    from slice_runner.infrastructure.process import Process

_RECORDED = "implementer-two-paths"


class Resolving:
    @staticmethod
    def resolved(
        process: Process,
        *,
        trace: RecordedTrace | None = None,
        tool_uses: RecordedToolUseRecorder | None = None,
    ) -> ConflictResolution:
        calls = HarnessInvocationRunner(
            process=process,
            telemetry=HarnessTelemetry(
                trace=trace or RecordedTrace(),
                turns=RecordedTurnLog(),
                spend_log=RecordedSpendLog(),
                tool_uses=tool_uses or RecordedToolUseRecorder(),
            ),
        )

        return ClaudeConflictResolver(calls=calls, reader=RecordedSourceReader()).resolve(
            MergeConflictMother.of_one_conflicting_file()
        )

    @staticmethod
    def carrying(report: dict[str, object]) -> RecordedProcess:
        return RecordedProcess(HarnessEnvelopeMother.carrying(report, recorded=_RECORDED))


class TestWhereTheProcessRuns:
    def test_the_worktree_becomes_the_working_directory_of_the_process(self) -> None:
        process = Resolving.carrying(ResolutionReportMother.valid())

        Resolving.resolved(process)

        assert process.cwd == MergeConflictMother.WORKTREE

    def test_the_harness_is_invoked_exactly_once_because_a_retry_is_a_decision_of_whoever_orchestrates(self) -> None:
        process = Resolving.carrying(ResolutionReportMother.valid())

        Resolving.resolved(process)

        assert process.calls == 1


class TestTheCallSubjectComesFromTheConflictsOwnArguments:
    def test_the_trace_carries_the_conflicts_own_repo_issue_and_slice_id_and_not_a_crossed_field(self) -> None:
        trace = RecordedTrace()

        Resolving.resolved(Resolving.carrying(ResolutionReportMother.valid()), trace=trace)

        recorded = trace.calls[0]
        assert (recorded.repo, recorded.issue, recorded.slice_id) == (
            MergeConflictMother.REPO,
            MergeConflictMother.ISSUE,
            MergeConflictMother.SLICE_ID,
        )

    def test_the_trace_records_the_call_under_the_catch_up_step_so_its_spend_lands_under_its_own_role(
        self,
    ) -> None:
        trace = RecordedTrace()

        Resolving.resolved(Resolving.carrying(ResolutionReportMother.valid()), trace=trace)

        assert trace.calls[0].step is Step.CATCH_UP

    def test_the_tool_use_recording_carries_the_conflicts_own_worktree_and_slice_id(self) -> None:
        tool_uses = RecordedToolUseRecorder()

        Resolving.resolved(Resolving.carrying(ResolutionReportMother.valid()), tool_uses=tool_uses)

        recorded = tool_uses.calls[0]
        assert (recorded.worktree, recorded.slice_id) == (MergeConflictMother.WORKTREE, MergeConflictMother.SLICE_ID)


class TestTheResolutionOfARecordedCall:
    def test_what_the_harness_spent_on_the_call_travels_with_the_resolution(self) -> None:
        resolution = Resolving.resolved(Resolving.carrying(ResolutionReportMother.valid()))

        assert resolution.spend == HarnessSpendMother.of_the_implementer_call()


class TestWhatTheCallIsAllowedToReturn:
    def test_a_report_missing_its_only_field_is_rejected_instead_of_passing_through_as_free_text(self) -> None:
        process = Resolving.carrying(ResolutionReportMother.without("summary"))

        with pytest.raises(InvalidResolutionReportError, match="summary"):
            Resolving.resolved(process)

    def test_a_rejected_call_still_reports_what_it_spent_so_the_budget_still_sees_it(self) -> None:
        missing = ResolutionReportMother.without("summary")

        with pytest.raises(InvalidResolutionReportError) as rejection:
            Resolving.resolved(Resolving.carrying(missing))

        assert rejection.value.spend == HarnessSpendMother.of_the_implementer_call()

    def test_a_permission_denied_mid_call_is_rejected_instead_of_trusting_an_unfinished_resolution(self) -> None:
        denying = HarnessEnvelopeMother.carrying(ResolutionReportMother.valid(), recorded=_RECORDED) | {
            "permission_denials": [dict(denial) for denial in HarnessEnvelopeMother.DENIALS_AS_THE_HARNESS_SENDS_THEM]
        }
        process = RecordedProcess(denying)

        with pytest.raises(PermissionDeniedError):
            Resolving.resolved(process)
