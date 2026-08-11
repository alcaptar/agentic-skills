from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

from slice_runner.application.actions.record_closure import RecordClosure, RecordClosureParams
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.metrics_log import MetricsLog
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
