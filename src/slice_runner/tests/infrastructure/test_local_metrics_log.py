from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.clock import Clock
from slice_runner.domain.diff_stats import DiffStats
from slice_runner.domain.exceptions import RunNotClosedError, UnreadableMetricsLogError
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity
from slice_runner.infrastructure import local_metrics_log
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.durable_ledger import DurableLedger
from slice_runner.infrastructure.local_metrics_log import LocalMetricsLog
from slice_runner.infrastructure.metrics_entry_payload import MetricsEntryPayload
from slice_runner.tests.infrastructure.retired_ledger_directory import RetiredLedgerDirectory
from slice_runner.tests.infrastructure.stub_ledger import WiredStubLedgers
from slice_runner.tests.mothers.closed_slice_mother import ClosedSliceMother
from slice_runner.tests.mothers.discarded_call_mother import DiscardedCallMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.verdict_mother import FindingMother

if TYPE_CHECKING:
    from pathlib import Path

_STAMP = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)


class WrittenMetricsLog:
    @staticmethod
    def rows_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "runs" / "metrics.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

    @staticmethod
    def row_under(root: Path) -> dict[str, object]:
        rows = WrittenMetricsLog.rows_under(root)
        if len(rows) != 1:
            raise AssertionError(f"expected exactly one row, found {len(rows)}")

        return rows[0]


class WithTheLedgerOutOfTheRealHome:
    @pytest.fixture(autouse=True)
    def ledger_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

    @staticmethod
    def frozen_at(stamp: datetime = _STAMP) -> Mock:
        clock: Mock = create_autospec(Clock, spec_set=True, instance=True)
        clock.now.return_value = stamp
        return clock


class TestWhereTheDurableLogIsWrittenFrom(WithTheLedgerOutOfTheRealHome):
    def test_the_log_is_written_by_the_program_itself_and_not_by_launching_a_process(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged())

        assert (tmp_path / "slice-runner" / "runs" / "metrics.jsonl").exists()


class TestHowEachClosureIsRecorded(WithTheLedgerOutOfTheRealHome):
    @pytest.mark.parametrize(
        ("state", "verdict", "ci"),
        [
            (RunState.MERGED, "pass", "green"),
            (RunState.BLOCKED_CI_RED, "pass", "red"),
            (RunState.BLOCKED_CI_INDETERMINATE, "pass", "none"),
            (RunState.BLOCKED_VERIFY, "fail", "none"),
            (RunState.BLOCKED_CONTROLS, "blocked-controls", "none"),
            (RunState.BLOCKED_HYGIENE, "blocked-hygiene", "none"),
            (RunState.ABORTED_BUDGET, "aborted-budget", "none"),
            (RunState.ABORTED_UNMEASURED_CALL, "aborted-unmeasured-call", "none"),
        ],
    )
    def test_every_closure_of_the_program_has_its_own_pair_in_the_durable_vocabulary(
        self, tmp_path: Path, state: RunState, verdict: str, ci: str
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.closed_as(state))

        row = WrittenMetricsLog.row_under(tmp_path)
        assert (row["verdict"], row["ci"]) == (verdict, ci)

    def test_a_budget_abort_is_recorded_with_a_cost_that_really_is_above_its_own_cap(self, tmp_path: Path) -> None:
        budgets = Budgets(slice_cost_usd=0.1)
        spend = HarnessSpendMother.of_the_implementer_call()

        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.aborted_over_budget(budgets, spend=spend))

        row = WrittenMetricsLog.row_under(tmp_path)
        harness = row["harness"]
        recorded_budgets = row["budgets"]
        assert isinstance(harness, dict)
        assert isinstance(recorded_budgets, dict)
        assert row["verdict"] == "aborted-budget"
        assert harness["cost_usd"] == spend.cost_usd
        assert harness["cost_usd"] > recorded_budgets["slice_cost_usd"]

    def test_a_run_that_has_not_closed_is_rejected_instead_of_written_as_a_row(self, tmp_path: Path) -> None:
        with pytest.raises(RunNotClosedError, match="one line per closed slice"):
            LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.still_open())

        assert not (tmp_path / "slice-runner" / "runs" / "metrics.jsonl").exists()

    def test_the_slice_travels_by_the_three_names_the_log_indexes_it_with(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged())

        row = WrittenMetricsLog.row_under(tmp_path)
        assert (row["repo"], row["slice_id"], row["name"]) == (
            ClosedSliceMother.REPO,
            ClosedSliceMother.SLICE_ID,
            ClosedSliceMother.NAME,
        )

    def test_the_row_also_carries_the_issue_of_the_subissue_it_closed(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged())

        assert WrittenMetricsLog.row_under(tmp_path)["issue"] == ClosedSliceMother.ISSUE

    def test_the_row_is_stamped_with_the_moment_the_clock_reads_when_it_closes(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at(_STAMP)).record(ClosedSliceMother.merged())

        assert WrittenMetricsLog.row_under(tmp_path)["ts"] == _STAMP.isoformat()


class TestWhatOfTheHarnessIsWritten(WithTheLedgerOutOfTheRealHome):
    def test_the_spend_of_every_call_of_the_slice_travels_summed_and_not_only_the_last_one(
        self, tmp_path: Path
    ) -> None:
        closed = ClosedSliceMother.merged_measuring(
            HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call()
        )

        LocalMetricsLog(clock=self.frozen_at()).record(closed)

        harness = WrittenMetricsLog.row_under(tmp_path)["harness"]
        assert harness == {
            "cost_usd": 0.3951979,
            "turns": 14,
            "duration_ms": 65652,
            "cache_read_tokens": 256813,
        }

    def test_with_nothing_measured_no_group_of_the_harness_is_written(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_measuring_nothing())

        assert "harness" not in WrittenMetricsLog.row_under(tmp_path)

    def test_the_model_the_harness_declares_travels_and_not_the_alias_the_program_requested(
        self, tmp_path: Path
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.merged_measuring(HarnessSpendMother.of_the_implementer_call())
        )

        assert WrittenMetricsLog.row_under(tmp_path)["models"] == ["claude-sonnet-5"]

    def test_a_slice_that_used_more_than_one_model_writes_every_one_of_them(self, tmp_path: Path) -> None:
        closed = ClosedSliceMother.merged_measuring(
            HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call()
        )

        LocalMetricsLog(clock=self.frozen_at()).record(closed)

        assert WrittenMetricsLog.row_under(tmp_path)["models"] == ["claude-haiku-4-5-20251001", "claude-sonnet-5"]

    def test_with_nothing_measured_no_model_is_written(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_measuring_nothing())

        assert "models" not in WrittenMetricsLog.row_under(tmp_path)


class TestWhatVariantIsWritten(WithTheLedgerOutOfTheRealHome):
    def test_every_row_the_program_writes_names_the_variant_that_is_conducting_the_slice(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged())

        assert WrittenMetricsLog.row_under(tmp_path)["variant"] == MetricsEntryPayload.VARIANT


class TestHowMuchTheSliceChanged(WithTheLedgerOutOfTheRealHome):
    def test_what_the_implementer_declared_left_out_travels_as_a_count_and_not_as_the_reasons(
        self, tmp_path: Path
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.merged_leaving_out("no cubri el binario", "falta el caso de rename")
        )

        assert WrittenMetricsLog.row_under(tmp_path)["debt"] == 2

    def test_a_slice_that_left_nothing_out_writes_zero_debt_instead_of_omitting_it(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged())

        assert WrittenMetricsLog.row_under(tmp_path)["debt"] == 0

    def test_the_size_of_the_diff_measured_at_the_verify_that_passed_travels_as_its_own_group(
        self, tmp_path: Path
    ) -> None:
        stats = DiffStats(files_changed=4, lines_added=51, lines_deleted=9)

        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_measuring_the_diff(stats))

        assert WrittenMetricsLog.row_under(tmp_path)["diff"] == {
            "files_changed": 4,
            "lines_added": 51,
            "lines_deleted": 9,
        }

    def test_a_closure_with_no_diff_measured_this_invocation_writes_no_group_instead_of_a_zero_one(
        self, tmp_path: Path
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged())

        assert "diff" not in WrittenMetricsLog.row_under(tmp_path)


class TestWhatConfigurationTheRunWasConductedWith(WithTheLedgerOutOfTheRealHome):
    def test_the_budgets_the_run_was_conducted_with_travel_whole_and_not_one_field_at_a_time(
        self, tmp_path: Path
    ) -> None:
        budgets = Budgets(slice_cost_usd=12.5, verify_retries=4)

        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_with_config(budgets=budgets))

        assert WrittenMetricsLog.row_under(tmp_path)["budgets"] == asdict(budgets)

    def test_the_model_assigned_to_each_role_travels_whole_and_not_one_field_at_a_time(self, tmp_path: Path) -> None:
        models = RoleModels(understand="haiku", implement="opus", verify="sonnet")

        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_with_config(models=models))

        row = WrittenMetricsLog.row_under(tmp_path)
        assert row["models_by_role"] == {"understand": "haiku", "implement": "opus", "verify": "sonnet"}

    def test_two_runs_with_different_configurations_write_rows_that_differ_on_that_configuration_and_not_only_on_cost(
        self, tmp_path: Path
    ) -> None:
        log = LocalMetricsLog(clock=self.frozen_at())
        same_budgets = Budgets(slice_cost_usd=10.0)
        first_models = RoleModels(understand="sonnet", implement="sonnet", verify="sonnet")
        second_models = RoleModels(understand="haiku", implement="opus", verify="haiku")

        log.record(ClosedSliceMother.merged_with_config(budgets=same_budgets, models=first_models))
        log.record(ClosedSliceMother.merged_with_config(budgets=same_budgets, models=second_models))

        rows = WrittenMetricsLog.rows_under(tmp_path)
        assert rows[0]["harness"] == rows[1]["harness"]
        assert rows[0]["models_by_role"] != rows[1]["models_by_role"]


class TestWhatTheRunAlreadyCounted(WithTheLedgerOutOfTheRealHome):
    def test_the_retries_of_implementing_are_the_sum_of_the_five_ways_back_to_that_step(self, tmp_path: Path) -> None:
        run = RunMother.that_went_back_for_every_reason()

        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_after_going_back_for_every_reason())

        assert WrittenMetricsLog.row_under(tmp_path)["implement_retries"] == (
            run.control_retries + run.hygiene_retries + run.verify_retries + run.correction_retries + run.ci_retries
        )

    def test_each_kind_of_retry_also_travels_on_its_own_so_the_sum_can_be_read_apart(self, tmp_path: Path) -> None:
        run = RunMother.that_went_back_for_every_reason()

        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_after_going_back_for_every_reason())

        row = WrittenMetricsLog.row_under(tmp_path)
        assert (row["control_retries"], row["verify_retries"], row["ci_retries"]) == (
            run.control_retries,
            run.verify_retries,
            run.ci_retries,
        )

    def test_the_retries_a_veto_spent_travel_apart_from_the_ones_a_round_of_corrections_spent(
        self, tmp_path: Path
    ) -> None:
        run = RunMother.that_went_back_for_every_reason()

        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_after_going_back_for_every_reason())

        row = WrittenMetricsLog.row_under(tmp_path)
        assert (row["verify_retries"], row["correction_retries"]) == (
            run.verify_retries,
            run.correction_retries,
        )
        assert row["verify_retries"] != row["correction_retries"]

    def test_the_findings_travel_counted_by_severity_and_not_as_a_single_total(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.vetoed_over(
                FindingMother.without_line(severity=Severity.HIGH),
                FindingMother.without_line(severity=Severity.LOW),
                FindingMother.without_line(severity=Severity.LOW),
            )
        )

        assert WrittenMetricsLog.row_under(tmp_path)["findings"] == {"high": 1, "medium": 0, "low": 2}

    def test_the_findings_of_the_last_round_travel_apart_so_a_pass_with_one_accumulated_is_never_ambiguous(
        self, tmp_path: Path
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.merged_after_correcting(FindingMother.without_line(severity=Severity.HIGH))
        )

        row = WrittenMetricsLog.row_under(tmp_path)
        assert row["findings"] == {"high": 1, "medium": 0, "low": 0}
        assert row["findings_of_the_last_round"] == {"high": 0, "medium": 0, "low": 0}


class TestWhyTheJudgeWasReinvoked(WithTheLedgerOutOfTheRealHome):
    @staticmethod
    def _discarded_call(row: dict[str, object]) -> dict[str, object]:
        discarded_call = row["discarded_call"]
        assert isinstance(discarded_call, dict)
        return discarded_call

    def test_the_cause_of_the_discards_travels_next_to_their_count(self, tmp_path: Path) -> None:
        run = RunMother.that_went_back_for_every_reason()

        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.merged_discarding_because_of(DiscardedCallMother.of_a_failed_call())
        )

        row = WrittenMetricsLog.row_under(tmp_path)
        assert row["verify_discards"] == run.verify_discards
        assert self._discarded_call(row)["cause"] == "failed-call"

    def test_the_step_of_the_discard_travels_next_to_its_cause(self, tmp_path: Path) -> None:
        discarded = DiscardedCallMother.of_a_failed_call()

        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_discarding_because_of(discarded))

        row = WrittenMetricsLog.row_under(tmp_path)
        assert self._discarded_call(row)["step"] == "verify"

    def test_an_incoherent_verdict_is_recorded_as_a_different_cause_than_a_call_that_never_answered(
        self, tmp_path: Path
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.merged_discarding_because_of(DiscardedCallMother.of_an_incoherent_verdict())
        )

        row = WrittenMetricsLog.row_under(tmp_path)
        assert self._discarded_call(row)["cause"] == "incoherent-verdict"

    def test_a_call_discarded_for_a_missing_structured_output_is_recorded_with_its_own_cause(
        self, tmp_path: Path
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.merged_discarding_because_of(DiscardedCallMother.of_a_missing_structured_output())
        )

        row = WrittenMetricsLog.row_under(tmp_path)
        assert self._discarded_call(row)["cause"] == "no-structured-output"

    def test_without_a_cause_only_the_count_travels_because_none_is_invented(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_discarding_because_of(None))

        row = WrittenMetricsLog.row_under(tmp_path)
        assert "verify_discards" in row
        assert "discarded_call" not in row


class TestWhyTheCiCouldNotBeRead(WithTheLedgerOutOfTheRealHome):
    def test_the_command_itself_failing_is_recorded_with_its_own_cause(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.blocked_indeterminate_because_of(CiIndeterminateCause.COMMAND_FAILED)
        )

        assert WrittenMetricsLog.row_under(tmp_path)["ci_indeterminate_cause"] == "command-failed"

    def test_an_unreadable_response_is_recorded_as_a_different_cause_than_a_failed_command(
        self, tmp_path: Path
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.blocked_indeterminate_because_of(CiIndeterminateCause.UNREADABLE_RESPONSE)
        )

        assert WrittenMetricsLog.row_under(tmp_path)["ci_indeterminate_cause"] == "unreadable-response"

    def test_without_a_cause_only_the_ci_field_travels_because_none_is_invented(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.blocked_indeterminate_because_of(None))

        row = WrittenMetricsLog.row_under(tmp_path)
        assert row["ci"] == "none"
        assert "ci_indeterminate_cause" not in row


class TestTheLedgerOnlyGrows(WithTheLedgerOutOfTheRealHome):
    def test_a_second_closure_is_appended_instead_of_overwriting_the_first(self, tmp_path: Path) -> None:
        log = LocalMetricsLog(clock=self.frozen_at())

        log.record(ClosedSliceMother.closed_as(RunState.MERGED))
        log.record(ClosedSliceMother.closed_as(RunState.BLOCKED_VERIFY))

        assert [row["verdict"] for row in WrittenMetricsLog.rows_under(tmp_path)] == ["pass", "fail"]


class TestReadingBackTheClosedSlices(WithTheLedgerOutOfTheRealHome):
    def test_a_slice_never_recorded_returns_nothing_instead_of_failing(self, tmp_path: Path) -> None:
        found = LocalMetricsLog(clock=self.frozen_at()).closed_slices(
            repo=None, since=datetime(2000, 1, 1, tzinfo=UTC), until=datetime(2100, 1, 1, tzinfo=UTC)
        )

        assert found == ()

    def test_every_closed_slice_within_the_window_is_returned_in_the_order_it_was_recorded(
        self, tmp_path: Path
    ) -> None:
        log = LocalMetricsLog(clock=self.frozen_at(datetime(2026, 1, 1, tzinfo=UTC)))
        log.record(ClosedSliceMother.closed_as(RunState.MERGED))
        log = LocalMetricsLog(clock=self.frozen_at(datetime(2026, 2, 1, tzinfo=UTC)))
        log.record(ClosedSliceMother.closed_as_for_issue(RunState.BLOCKED_VERIFY, issue=ClosedSliceMother.ISSUE + 1))

        found = log.closed_slices(
            repo=None, since=datetime(2000, 1, 1, tzinfo=UTC), until=datetime(2100, 1, 1, tzinfo=UTC)
        )

        assert [record.state for record in found] == [RunState.MERGED, RunState.BLOCKED_VERIFY]

    def test_a_slice_outside_the_date_range_is_left_out(self, tmp_path: Path) -> None:
        log = LocalMetricsLog(clock=self.frozen_at(datetime(2026, 1, 1, tzinfo=UTC)))
        log.record(ClosedSliceMother.merged())

        found = log.closed_slices(
            repo=None, since=datetime(2026, 2, 1, tzinfo=UTC), until=datetime(2026, 3, 1, tzinfo=UTC)
        )

        assert found == ()

    def test_a_slice_of_a_different_repo_is_left_out_when_a_repo_is_asked_for(self, tmp_path: Path) -> None:
        log = LocalMetricsLog(clock=self.frozen_at())
        log.record(ClosedSliceMother.merged())

        found = log.closed_slices(
            repo="another/repo", since=datetime(2000, 1, 1, tzinfo=UTC), until=datetime(2100, 1, 1, tzinfo=UTC)
        )

        assert found == ()

    def test_without_a_repo_every_repo_in_the_window_is_returned(self, tmp_path: Path) -> None:
        log = LocalMetricsLog(clock=self.frozen_at())
        log.record(ClosedSliceMother.merged())

        found = log.closed_slices(
            repo=ClosedSliceMother.REPO, since=datetime(2000, 1, 1, tzinfo=UTC), until=datetime(2100, 1, 1, tzinfo=UTC)
        )

        assert [record.repo for record in found] == [ClosedSliceMother.REPO]

    def test_a_slice_measuring_spend_models_variant_and_diff_is_read_back_with_all_of_it_and_not_only_its_state(
        self, tmp_path: Path
    ) -> None:
        stats = DiffStats(files_changed=4, lines_added=51, lines_deleted=9)
        implementer_spend = HarnessSpendMother.of_the_implementer_call()
        judge_spend = HarnessSpendMother.of_the_judge_call()
        closed = ClosedSliceMother.merged_measuring_the_diff_and_spend(stats, implementer_spend, judge_spend)
        log = LocalMetricsLog(clock=self.frozen_at())

        log.record(closed)

        found = log.closed_slices(
            repo=None, since=datetime(2000, 1, 1, tzinfo=UTC), until=datetime(2100, 1, 1, tzinfo=UTC)
        )

        assert len(found) == 1
        record = found[0]
        assert record.variant == MetricsEntryPayload.VARIANT
        assert set(record.models) == {*implementer_spend.models, *judge_spend.models}
        assert record.spend is not None
        assert record.spend.cost_usd == closed.spend.cost_usd
        assert record.diff == stats

    def test_a_line_that_is_not_json_is_refused_instead_of_being_skipped_in_silence(self, tmp_path: Path) -> None:
        log = LocalMetricsLog(clock=self.frozen_at())
        log.record(ClosedSliceMother.merged())
        ledger = tmp_path / "slice-runner" / "runs" / "metrics.jsonl"
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write("not json\n")

        with pytest.raises(UnreadableMetricsLogError):
            log.closed_slices(repo=None, since=datetime(2000, 1, 1, tzinfo=UTC), until=datetime(2100, 1, 1, tzinfo=UTC))


class TestDeduplicatingRepeatedClosuresOfTheSameSlice(WithTheLedgerOutOfTheRealHome):
    def test_two_closures_of_the_same_slice_within_the_window_collapse_into_the_last_one_written(
        self, tmp_path: Path
    ) -> None:
        log = LocalMetricsLog(clock=self.frozen_at(datetime(2026, 1, 1, tzinfo=UTC)))
        log.record(ClosedSliceMother.closed_as(RunState.BLOCKED_VERIFY))
        log = LocalMetricsLog(clock=self.frozen_at(datetime(2026, 1, 2, tzinfo=UTC)))
        log.record(ClosedSliceMother.closed_as(RunState.MERGED))

        found = log.closed_slices(
            repo=None, since=datetime(2000, 1, 1, tzinfo=UTC), until=datetime(2100, 1, 1, tzinfo=UTC)
        )

        assert [record.state for record in found] == [RunState.MERGED]

    def test_a_window_that_only_covers_the_earlier_closure_still_returns_it_instead_of_reaching_past_it(
        self, tmp_path: Path
    ) -> None:
        log = LocalMetricsLog(clock=self.frozen_at(datetime(2026, 8, 8, tzinfo=UTC)))
        log.record(ClosedSliceMother.closed_as(RunState.BLOCKED_VERIFY))
        log = LocalMetricsLog(clock=self.frozen_at(datetime(2026, 8, 18, tzinfo=UTC)))
        log.record(ClosedSliceMother.closed_as(RunState.MERGED))

        found = log.closed_slices(
            repo=None, since=datetime(2026, 8, 8, tzinfo=UTC), until=datetime(2026, 8, 14, tzinfo=UTC)
        )

        assert [record.state for record in found] == [RunState.BLOCKED_VERIFY]

    def test_the_key_is_the_repo_and_the_issue_and_not_the_slice_id_that_can_change_mid_feature(
        self, tmp_path: Path
    ) -> None:
        log = LocalMetricsLog(clock=self.frozen_at(datetime(2026, 1, 1, tzinfo=UTC)))
        log.record(ClosedSliceMother.merged())
        log = LocalMetricsLog(clock=self.frozen_at(datetime(2026, 1, 2, tzinfo=UTC)))
        log.record(ClosedSliceMother.merged_with_a_user_story_key())

        found = log.closed_slices(
            repo=None, since=datetime(2000, 1, 1, tzinfo=UTC), until=datetime(2100, 1, 1, tzinfo=UTC)
        )

        assert [record.slice_id for record in found] == ["PROJ-1234-07"]


class TestTheRetiredLogDirectoryIsNeverTouched(WithTheLedgerOutOfTheRealHome):
    def test_a_closure_written_under_the_retired_directory_is_neither_found_nor_touched(self, tmp_path: Path) -> None:
        old_ledger = RetiredLedgerDirectory.path(tmp_path, "metrics")
        old_line = (
            json.dumps(MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract())
            + "\n"
        ).encode("utf-8")
        RetiredLedgerDirectory.seeded_without_opening(old_ledger, old_line)

        found = LocalMetricsLog(clock=self.frozen_at()).closed_slices(
            repo=None, since=datetime(2000, 1, 1, tzinfo=UTC), until=datetime(2100, 1, 1, tzinfo=UTC)
        )

        assert found == ()
        assert RetiredLedgerDirectory.read_without_opening(old_ledger) == old_line


class TestWhereTheLedgerLives:
    def test_the_directory_is_created_when_it_is_not_there_so_the_first_row_is_not_lost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "never-used-before"))

        LocalMetricsLog(clock=WithTheLedgerOutOfTheRealHome.frozen_at()).record(ClosedSliceMother.merged())

        assert (tmp_path / "never-used-before" / "slice-runner" / "runs" / "metrics.jsonl").exists()

    def test_the_ledger_path_is_composed_under_runs_and_not_under_the_retired_log_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        path = DurableLedger(name=LocalMetricsLog.LEDGER, row=MetricsEntryPayload).path()

        assert path == tmp_path / "slice-runner" / "runs" / "metrics.jsonl"


class TestTheAdapterOwnsOnlyItsNameAndItsPayload:
    def test_recording_a_closure_reaches_only_the_ledger_and_writes_no_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        created = WiredStubLedgers.on(local_metrics_log, monkeypatch)

        LocalMetricsLog(clock=WithTheLedgerOutOfTheRealHome.frozen_at()).record(ClosedSliceMother.merged())

        assert len(created) == 1
        stub = created[0]
        assert stub.name == LocalMetricsLog.LEDGER
        assert stub.row is MetricsEntryPayload
        assert len(stub.appended) == 1
        assert not (tmp_path / "slice-runner").exists()
