from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

from slice_runner.application.actions.record_closure import RecordClosure, RecordClosureParams
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.diff_stats import DiffStats
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.metrics_log import MetricsLog
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity
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

    @property
    def action(self) -> RecordClosure:
        return RecordClosure(metrics=self.metrics)

    def close(self, **overrides: object) -> ClosedSlice:
        params = {
            "repo": _REPO,
            "issue": _ISSUE,
            "slice_id": _SLICE,
            "name": _NAME,
            "state": RunState.MERGED,
            "run": RunMother.awaiting_merge(),
            "budgets": Budgets(),
            "models": RoleModels(understand="sonnet", implement="sonnet"),
            "spends": (HarnessSpendMother.of_the_implementer_call(),),
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

        written = closer.close(discard_cause=DiscardCause.INCOHERENT_VERDICT)

        assert written.discard_cause is DiscardCause.INCOHERENT_VERDICT

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
        models = RoleModels(understand="haiku", implement="opus")

        written = closer.close(models=models)

        assert written.models == models


class TestWhichSpendsCount:
    def test_a_spend_that_was_never_measured_does_not_enter_the_row_instead_of_counting_as_zero(self) -> None:
        closer = _Closer()

        written = closer.close(spends=(HarnessSpend.nothing(),))

        assert written.spends == ()

    def test_the_measured_spends_are_kept_in_the_order_they_were_paid(self) -> None:
        closer = _Closer()
        first = HarnessSpendMother.of_the_understanding_call()
        second = HarnessSpendMother.of_the_implementer_call()

        written = closer.close(spends=(first, second))

        assert written.spends == (first, second)

    def test_an_unmeasured_spend_between_two_measured_ones_is_dropped_without_dropping_the_others(self) -> None:
        closer = _Closer()
        first = HarnessSpendMother.of_the_understanding_call()
        last = HarnessSpendMother.of_the_judge_call()

        written = closer.close(spends=(first, HarnessSpend.nothing(), last))

        assert written.spends == (first, last)
