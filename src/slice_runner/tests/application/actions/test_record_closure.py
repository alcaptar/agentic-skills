from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

from slice_runner.application.actions.record_closure import RecordClosure, RecordClosureParams
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.call_spend_log import CallSpendLog
from slice_runner.domain.call_trace import CallTrace
from slice_runner.domain.diff_stats import DiffStats
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.metrics_log import MetricsLog
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.run_repository import RunRepository
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity
from slice_runner.tests.mothers.discarded_call_mother import DiscardedCallMother
from slice_runner.tests.mothers.harness_call_mother import HarnessCallMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.verdict_mother import FindingMother

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice import ClosedSlice

_REPO = "alcaptar/agentic-skills"
_ISSUE = 38
_SLICE = "slice-07"
_NAME = "una-llamada-una-fila"


class _Closer:
    def __init__(self) -> None:
        self.metrics: Mock = create_autospec(MetricsLog, spec_set=True, instance=True)
        self.repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        self.trace: Mock = create_autospec(CallTrace, spec_set=True, instance=True)
        self.trace.calls_of.return_value = ()
        self.spend_log: Mock = create_autospec(CallSpendLog, spec_set=True, instance=True)
        self.spend_log.spend_of.return_value = HarnessSpend.nothing()

    @property
    def action(self) -> RecordClosure:
        return RecordClosure(
            metrics=self.metrics, repository=self.repository, trace=self.trace, spend_log=self.spend_log
        )

    def close(self, **overrides: object) -> ClosedSlice:
        params = {
            "repo": _REPO,
            "issue": _ISSUE,
            "slice_id": _SLICE,
            "name": _NAME,
            "state": RunState.MERGED,
            "run": RunMother.awaiting_merge(),
            "budgets": Budgets(),
            "models": RoleModels(understand="sonnet", implement="sonnet", verify="sonnet"),
            **overrides,
        }
        self.action.execute(RecordClosureParams(**params))  # type: ignore[arg-type]
        written: ClosedSlice = self.metrics.record.call_args.args[0]

        return written


class TestTheRowItWrites:
    def test_the_row_names_the_slice_and_the_state_the_run_closed_in(self) -> None:
        closer = _Closer()

        written = closer.close(state=RunState.BLOCKED_VERIFY)

        assert written.repo == _REPO
        assert written.slice_id == _SLICE
        assert written.name == _NAME
        assert written.state is RunState.BLOCKED_VERIFY

    def test_the_findings_of_every_round_and_of_the_last_one_travel_apart_so_a_fixed_one_is_not_lost(self) -> None:
        closer = _Closer()
        every = (FindingMother.without_line(), FindingMother.low_severity())
        last = (FindingMother.low_severity(),)

        written = closer.close(findings=every, findings_of_the_last_round=last)

        assert written.count_findings(Severity.HIGH) == 1
        assert written.count_findings_of_the_last_round(Severity.HIGH) == 0

    def test_the_cause_of_a_discarded_verdict_reaches_the_row(self) -> None:
        closer = _Closer()
        discarded = DiscardedCallMother.of_an_incoherent_verdict()

        written = closer.close(discarded_call=discarded)

        assert written.discarded_call == discarded

    def test_what_the_implementer_declared_left_out_reaches_the_row(self) -> None:
        closer = _Closer()

        written = closer.close(debt=("no cubri el caso de un binario",))

        assert written.debt == ("no cubri el caso de un binario",)

    def test_a_run_with_nothing_left_out_writes_an_empty_debt_instead_of_omitting_it(self) -> None:
        closer = _Closer()

        written = closer.close()

        assert written.debt == ()

    def test_the_size_of_the_diff_measured_at_the_last_verify_reaches_the_row(self) -> None:
        closer = _Closer()
        stats = DiffStats(files_changed=3, lines_added=40, lines_deleted=12)

        written = closer.close(diff_stats=stats)

        assert written.diff_stats == stats

    def test_a_closure_with_no_verify_measured_this_invocation_carries_no_diff_stats_instead_of_a_zero_one(
        self,
    ) -> None:
        closer = _Closer()

        written = closer.close()

        assert written.diff_stats is None

    def test_the_budgets_the_run_was_conducted_with_reach_the_row(self) -> None:
        closer = _Closer()
        budgets = Budgets(slice_cost_usd=12.5)

        written = closer.close(budgets=budgets)

        assert written.budgets == budgets

    def test_the_model_assigned_to_each_role_reaches_the_row(self) -> None:
        closer = _Closer()
        models = RoleModels(understand="haiku", implement="opus", verify="haiku")

        written = closer.close(models=models)

        assert written.models == models


class TestWhichSpendsCount:
    def test_the_row_asks_the_trace_for_the_calls_of_this_slice_and_writes_what_the_spend_log_sums(self) -> None:
        closer = _Closer()
        closer.trace.calls_of.return_value = (HarnessCallMother.of_the_implementer(),)
        closer.spend_log.spend_of.return_value = HarnessSpendMother.of_the_implementer_call()

        written = closer.close()

        closer.trace.calls_of.assert_called_once_with(repo=_REPO, issue=_ISSUE, slice_id=_SLICE)
        closer.spend_log.spend_of.assert_called_once_with((HarnessCallMother.SESSION_OF_THE_IMPLEMENTER,))
        assert written.spend == HarnessSpendMother.of_the_implementer_call()

    def test_two_invocations_traced_with_distinct_sessions_are_each_summed_once_and_not_dropped(self) -> None:
        closer = _Closer()
        closer.trace.calls_of.return_value = (HarnessCallMother.of_the_implementer(), HarnessCallMother.of_the_judge())
        closer.spend_log.spend_of.return_value = HarnessSpend.summing(
            (HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call())
        )

        written = closer.close()

        closer.spend_log.spend_of.assert_called_once_with(
            (HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, HarnessCallMother.SESSION_OF_THE_JUDGE)
        )
        assert written.spend == HarnessSpend.summing(
            (HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call())
        )

    def test_the_spend_the_persisted_run_already_carries_is_not_added_on_top_of_the_trace_and_the_log(self) -> None:
        closer = _Closer()
        already_on_the_run = HarnessSpendMother.of_the_understanding_call()
        closer.trace.calls_of.return_value = (HarnessCallMother.of_the_implementer(), HarnessCallMother.of_the_judge())
        closer.spend_log.spend_of.return_value = HarnessSpend.summing(
            (HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call())
        )

        written = closer.close(run=RunMother.judging_after_spending(already_on_the_run))

        assert written.spend == HarnessSpend.summing(
            (HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call())
        )

    def test_a_spend_log_with_nothing_measured_leaves_the_row_with_no_spend_instead_of_a_zero_one(self) -> None:
        closer = _Closer()

        written = closer.close()

        assert written.spends == ()

    def test_a_call_that_cost_nothing_but_was_measured_still_reaches_the_row_instead_of_being_treated_as_unmeasured(
        self,
    ) -> None:
        closer = _Closer()
        closer.trace.calls_of.return_value = (HarnessCallMother.of_the_implementer(),)
        free_call = HarnessSpendMother.of_a_call_that_cost_nothing()
        closer.spend_log.spend_of.return_value = free_call

        written = closer.close()

        assert written.spends == (free_call,)


class TestPublishingTheCatchUpConflict:
    def test_a_closure_by_conflict_with_paths_publishes_them(self) -> None:
        closer = _Closer()
        paths = ("shared.txt", "src/module.py")

        closer.close(state=RunState.BLOCKED_CI_CONFLICT, conflicting_paths=paths)

        closer.repository.publish_catch_up_conflict.assert_called_once_with(repo=_REPO, issue=_ISSUE, paths=paths)

    def test_a_closure_by_conflict_with_no_paths_publishes_nothing(self) -> None:
        closer = _Closer()

        closer.close(state=RunState.BLOCKED_CI_CONFLICT, conflicting_paths=())

        closer.repository.publish_catch_up_conflict.assert_not_called()

    def test_a_closure_in_another_state_never_publishes_even_if_conflicting_paths_arrived(self) -> None:
        closer = _Closer()

        closer.close(state=RunState.MERGED, conflicting_paths=("shared.txt",))

        closer.repository.publish_catch_up_conflict.assert_not_called()


class TestPublishingTheVetoFindings:
    def test_a_closure_by_veto_with_findings_of_the_last_round_publishes_them(self) -> None:
        closer = _Closer()
        last = (FindingMother.without_line(), FindingMother.low_severity())

        closer.close(state=RunState.BLOCKED_VERIFY, findings_of_the_last_round=last)

        closer.repository.publish_findings.assert_called_once_with(repo=_REPO, issue=_ISSUE, findings=last)

    def test_a_closure_by_veto_with_no_findings_of_the_last_round_publishes_nothing(self) -> None:
        closer = _Closer()

        closer.close(state=RunState.BLOCKED_VERIFY, findings_of_the_last_round=())

        closer.repository.publish_findings.assert_not_called()

    def test_a_closure_in_another_state_never_publishes_even_if_findings_of_the_last_round_arrived(self) -> None:
        closer = _Closer()
        last = (FindingMother.without_line(),)

        closer.close(state=RunState.MERGED, findings_of_the_last_round=last)

        closer.repository.publish_findings.assert_not_called()
