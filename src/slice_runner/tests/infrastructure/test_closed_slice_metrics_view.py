from __future__ import annotations

from datetime import UTC, datetime

from slice_runner.domain.diff_stats import DiffStats
from slice_runner.domain.role_spend import RoleSpend
from slice_runner.domain.step import Step
from slice_runner.infrastructure.closed_slice_metrics_view import ClosedSliceMetricsView
from slice_runner.tests.mothers.closed_slice_record_mother import ClosedSliceRecordMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother

_SINCE = datetime(2026, 1, 1, tzinfo=UTC)
_UNTIL = datetime(2026, 12, 31, tzinfo=UTC)


class TestTheHeaderOfTheView:
    def test_the_scope_and_the_count_of_records_are_declared(self) -> None:
        records = (ClosedSliceRecordMother.merged(), ClosedSliceRecordMother.merged())

        rendered = ClosedSliceMetricsView.rendered(
            repo="alcaptar/agentic-skills", since=_SINCE, until=_UNTIL, records=records, role_spend=()
        )

        assert "alcaptar/agentic-skills" in rendered
        assert _SINCE.isoformat() in rendered
        assert _UNTIL.isoformat() in rendered
        assert "2" in rendered

    def test_a_scope_with_no_repo_says_every_repo_instead_of_a_blank(self) -> None:
        rendered = ClosedSliceMetricsView.rendered(repo=None, since=_SINCE, until=_UNTIL, records=(), role_spend=())

        assert "every repo" in rendered


class TestTheGapsTheDataCannotFill:
    def test_the_three_known_gaps_are_declared_regardless_of_what_is_in_the_window(self) -> None:
        rendered = ClosedSliceMetricsView.rendered(repo=None, since=_SINCE, until=_UNTIL, records=(), role_spend=())

        assert "diff size" in rendered
        assert "configuration" in rendered
        assert "input and output tokens" in rendered


class TestWhatTheLedgerLetsCountTwice:
    def test_two_rows_that_close_the_same_slice_are_both_listed_with_their_count(self) -> None:
        first = ClosedSliceRecordMother.merged()
        second = ClosedSliceRecordMother.merged()

        rendered = ClosedSliceMetricsView.rendered(
            repo=None, since=_SINCE, until=_UNTIL, records=(first, second), role_spend=()
        )

        assert f'data-slice-id="{first.slice_id}" data-rows="2"' in rendered

    def test_a_window_with_no_repeated_slice_says_so_instead_of_omitting_the_section(self) -> None:
        rendered = ClosedSliceMetricsView.rendered(
            repo=None, since=_SINCE, until=_UNTIL, records=(ClosedSliceRecordMother.merged(),), role_spend=()
        )

        assert "no slice was recorded more than once" in rendered


class TestCostAgainstSize:
    def test_a_record_with_both_size_and_spend_measured_is_plotted(self) -> None:
        stats = DiffStats(files_changed=4, lines_added=51, lines_deleted=9)
        record = ClosedSliceRecordMother.merged_measuring_the_diff(stats)

        rendered = ClosedSliceMetricsView.rendered(
            repo=None, since=_SINCE, until=_UNTIL, records=(record,), role_spend=()
        )

        assert f'data-slice-id="{record.slice_id}" data-lines="60" data-cost-usd="{record.spend.cost_usd}"' in rendered  # type: ignore[union-attr]

    def test_a_record_missing_the_diff_is_left_out_of_this_chart(self) -> None:
        record = ClosedSliceRecordMother.merged()

        rendered = ClosedSliceMetricsView.rendered(
            repo=None, since=_SINCE, until=_UNTIL, records=(record,), role_spend=()
        )

        assert "data-lines=" not in rendered

    def test_an_empty_chart_says_so_instead_of_rendering_nothing(self) -> None:
        rendered = ClosedSliceMetricsView.rendered(repo=None, since=_SINCE, until=_UNTIL, records=(), role_spend=())

        assert "no slice in this window measured both its size and its spend" in rendered


class TestSpendByRole:
    def test_one_bar_is_drawn_per_role_with_its_cost(self) -> None:
        role_spend = (
            RoleSpend(step=Step.IMPLEMENT, spend=HarnessSpendMother.of_the_implementer_call()),
            RoleSpend(step=Step.VERIFY, spend=HarnessSpendMother.of_the_judge_call()),
        )

        rendered = ClosedSliceMetricsView.rendered(
            repo=None, since=_SINCE, until=_UNTIL, records=(), role_spend=role_spend
        )

        assert f'data-step="implement" data-cost-usd="{HarnessSpendMother.of_the_implementer_call().cost_usd}"' in (
            rendered
        )
        assert f'data-step="verify" data-cost-usd="{HarnessSpendMother.of_the_judge_call().cost_usd}"' in rendered

    def test_no_role_spend_says_so_instead_of_rendering_nothing(self) -> None:
        rendered = ClosedSliceMetricsView.rendered(repo=None, since=_SINCE, until=_UNTIL, records=(), role_spend=())

        assert "no call was traced in this window" in rendered


class TestHowTheRoundsEvolveOverTime:
    def test_every_record_is_plotted_against_its_own_moment_in_chronological_order(self) -> None:
        later = ClosedSliceRecordMother.merged_at(datetime(2026, 6, 1, tzinfo=UTC))
        earlier = ClosedSliceRecordMother.merged_at(datetime(2026, 1, 1, tzinfo=UTC))

        rendered = ClosedSliceMetricsView.rendered(
            repo=None, since=_SINCE, until=_UNTIL, records=(later, earlier), role_spend=()
        )

        assert rendered.index(earlier.ts.isoformat()) < rendered.index(later.ts.isoformat())

    def test_the_rounds_of_a_record_are_the_sum_of_every_way_back_to_implementing(self) -> None:
        record = ClosedSliceRecordMother.merged_after_retrying(implement_retries=3, verify_retries=1)

        rendered = ClosedSliceMetricsView.rendered(
            repo=None, since=_SINCE, until=_UNTIL, records=(record,), role_spend=()
        )

        assert f'data-slice-id="{record.slice_id}" data-ts="{record.ts.isoformat()}" data-rounds="3"' in rendered
