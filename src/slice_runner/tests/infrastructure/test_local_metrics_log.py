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
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.exceptions import RunNotClosedError
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.local_metrics_log import LocalMetricsLog
from slice_runner.tests.mothers.closed_slice_mother import ClosedSliceMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.verdict_mother import FindingMother

if TYPE_CHECKING:
    from pathlib import Path

_STAMP = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)


class WrittenMetricsLog:
    @staticmethod
    def rows_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "metrics.jsonl"

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

        assert (tmp_path / "slice-runner" / "metrics.jsonl").exists()


class TestHowEachClosureIsRecorded(WithTheLedgerOutOfTheRealHome):
    @pytest.mark.parametrize(
        ("state", "verdict", "ci"),
        [
            (RunState.MERGED, "PASA", "green"),
            (RunState.BLOCKED_CI_RED, "PASA", "red"),
            (RunState.BLOCKED_CI_INDETERMINATE, "PASA", "none"),
            (RunState.BLOCKED_VERIFY, "FALLA", "none"),
            (RunState.BLOCKED_CONTROLS, "bloqueada-controles", "none"),
            (RunState.BLOCKED_HYGIENE, "bloqueada-higiene", "none"),
            (RunState.ABORTED_BUDGET, "abortada-presupuesto", "none"),
        ],
    )
    def test_every_closure_of_the_program_has_its_own_pair_in_the_durable_vocabulary(
        self, tmp_path: Path, state: RunState, verdict: str, ci: str
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.closed_as(state))

        row = WrittenMetricsLog.row_under(tmp_path)
        assert (row["veredicto"], row["ci"]) == (verdict, ci)

    def test_a_run_that_has_not_closed_is_rejected_instead_of_written_as_a_row(self, tmp_path: Path) -> None:
        with pytest.raises(RunNotClosedError, match="one line per closed slice"):
            LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.still_open())

        assert not (tmp_path / "slice-runner" / "metrics.jsonl").exists()

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
            "coste_usd": 0.3951979,
            "turnos": 14,
            "duracion_ms": 65652,
            "tokens_cache": 256813,
        }

    def test_with_nothing_measured_no_group_of_the_harness_is_written(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_measuring_nothing())

        assert "harness" not in WrittenMetricsLog.row_under(tmp_path)

    def test_the_wall_clock_duration_is_never_written_as_a_number_because_nothing_here_measures_it(
        self, tmp_path: Path
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.merged_measuring(HarnessSpendMother.of_the_judge_call())
        )

        assert WrittenMetricsLog.row_under(tmp_path)["duracion_s"] is None

    def test_the_token_count_is_never_written_as_a_number_either_because_the_envelope_does_not_bring_it(
        self, tmp_path: Path
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.merged_measuring(HarnessSpendMother.of_the_judge_call())
        )

        assert WrittenMetricsLog.row_under(tmp_path)["coste_tokens"] is None

    def test_the_model_the_harness_declares_travels_and_not_the_alias_the_program_requested(
        self, tmp_path: Path
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.merged_measuring(HarnessSpendMother.of_the_implementer_call())
        )

        assert WrittenMetricsLog.row_under(tmp_path)["modelos"] == ["claude-sonnet-5"]

    def test_a_slice_that_used_more_than_one_model_writes_every_one_of_them(self, tmp_path: Path) -> None:
        closed = ClosedSliceMother.merged_measuring(
            HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call()
        )

        LocalMetricsLog(clock=self.frozen_at()).record(closed)

        assert WrittenMetricsLog.row_under(tmp_path)["modelos"] == ["claude-haiku-4-5-20251001", "claude-sonnet-5"]

    def test_with_nothing_measured_no_model_is_written(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_measuring_nothing())

        assert "modelos" not in WrittenMetricsLog.row_under(tmp_path)


class TestWhatVariantIsWritten(WithTheLedgerOutOfTheRealHome):
    def test_every_row_the_program_writes_names_the_variant_that_is_conducting_the_slice(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged())

        assert WrittenMetricsLog.row_under(tmp_path)["variante"] == "programa"


class TestHowMuchTheSliceChanged(WithTheLedgerOutOfTheRealHome):
    def test_what_the_implementer_declared_left_out_travels_as_a_count_and_not_as_the_reasons(
        self, tmp_path: Path
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.merged_leaving_out("no cubri el binario", "falta el caso de rename")
        )

        assert WrittenMetricsLog.row_under(tmp_path)["deuda"] == 2

    def test_a_slice_that_left_nothing_out_writes_zero_debt_instead_of_omitting_it(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged())

        assert WrittenMetricsLog.row_under(tmp_path)["deuda"] == 0

    def test_the_size_of_the_diff_measured_at_the_verify_that_passed_travels_as_its_own_group(
        self, tmp_path: Path
    ) -> None:
        stats = DiffStats(files_changed=4, lines_added=51, lines_deleted=9)

        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_measuring_the_diff(stats))

        assert WrittenMetricsLog.row_under(tmp_path)["diff"] == {
            "ficheros": 4,
            "lineas_anadidas": 51,
            "lineas_borradas": 9,
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

        assert WrittenMetricsLog.row_under(tmp_path)["presupuestos"] == asdict(budgets)

    def test_the_model_assigned_to_each_role_travels_whole_and_not_one_field_at_a_time(self, tmp_path: Path) -> None:
        models = RoleModels(understand="haiku", implement="opus")

        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_with_config(models=models))

        row = WrittenMetricsLog.row_under(tmp_path)
        assert row["modelos_por_papel"] == {"understand": "haiku", "implement": "opus"}

    def test_two_runs_with_different_configurations_write_rows_that_differ_on_that_configuration_and_not_only_on_cost(
        self, tmp_path: Path
    ) -> None:
        log = LocalMetricsLog(clock=self.frozen_at())
        same_budgets = Budgets(slice_cost_usd=10.0)
        first_models = RoleModels(understand="sonnet", implement="sonnet")
        second_models = RoleModels(understand="haiku", implement="opus")

        log.record(ClosedSliceMother.merged_with_config(budgets=same_budgets, models=first_models))
        log.record(ClosedSliceMother.merged_with_config(budgets=same_budgets, models=second_models))

        rows = WrittenMetricsLog.rows_under(tmp_path)
        assert rows[0]["harness"] == rows[1]["harness"]
        assert rows[0]["modelos_por_papel"] != rows[1]["modelos_por_papel"]


class TestWhatTheRunAlreadyCounted(WithTheLedgerOutOfTheRealHome):
    def test_the_retries_of_implementing_are_the_sum_of_the_five_ways_back_to_that_step(self, tmp_path: Path) -> None:
        run = RunMother.that_went_back_for_every_reason()

        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_after_going_back_for_every_reason())

        assert WrittenMetricsLog.row_under(tmp_path)["reintentos_implement"] == (
            run.control_retries + run.hygiene_retries + run.verify_retries + run.correction_retries + run.ci_retries
        )

    def test_each_kind_of_retry_also_travels_on_its_own_so_the_sum_can_be_read_apart(self, tmp_path: Path) -> None:
        run = RunMother.that_went_back_for_every_reason()

        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_after_going_back_for_every_reason())

        row = WrittenMetricsLog.row_under(tmp_path)
        assert (row["reintentos_controles"], row["reintentos_verify"], row["reintentos_ci"]) == (
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
        assert (row["reintentos_verify"], row["reintentos_correcciones"]) == (
            run.verify_retries,
            run.correction_retries,
        )
        assert row["reintentos_verify"] != row["reintentos_correcciones"]

    def test_the_findings_travel_counted_by_severity_and_not_as_a_single_total(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.vetoed_over(
                FindingMother.without_line(severity=Severity.HIGH),
                FindingMother.without_line(severity=Severity.LOW),
                FindingMother.without_line(severity=Severity.LOW),
            )
        )

        assert WrittenMetricsLog.row_under(tmp_path)["hallazgos"] == {"alta": 1, "media": 0, "baja": 2}

    def test_the_findings_of_the_last_round_travel_apart_so_a_pass_with_one_accumulated_is_never_ambiguous(
        self, tmp_path: Path
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.merged_after_correcting(FindingMother.without_line(severity=Severity.HIGH))
        )

        row = WrittenMetricsLog.row_under(tmp_path)
        assert row["hallazgos"] == {"alta": 1, "media": 0, "baja": 0}
        assert row["hallazgos_ronda_final"] == {"alta": 0, "media": 0, "baja": 0}


class TestWhyTheJudgeWasReinvoked(WithTheLedgerOutOfTheRealHome):
    def test_the_cause_of_the_discards_travels_next_to_their_count(self, tmp_path: Path) -> None:
        run = RunMother.that_went_back_for_every_reason()

        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.merged_discarding_because_of(DiscardCause.FAILED_CALL)
        )

        row = WrittenMetricsLog.row_under(tmp_path)
        assert (row["descartes_verify"], row["descartes_verify_causa"]) == (run.verify_discards, "llamada-fallida")

    def test_an_incoherent_verdict_is_recorded_as_a_different_cause_than_a_call_that_never_answered(
        self, tmp_path: Path
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.merged_discarding_because_of(DiscardCause.INCOHERENT_VERDICT)
        )

        assert WrittenMetricsLog.row_under(tmp_path)["descartes_verify_causa"] == "veredicto-incoherente"

    def test_without_a_cause_only_the_count_travels_because_none_is_invented(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.merged_discarding_because_of(None))

        row = WrittenMetricsLog.row_under(tmp_path)
        assert "descartes_verify" in row
        assert "descartes_verify_causa" not in row


class TestWhyTheCiCouldNotBeRead(WithTheLedgerOutOfTheRealHome):
    def test_the_command_itself_failing_is_recorded_with_its_own_cause(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.blocked_indeterminate_because_of(CiIndeterminateCause.COMMAND_FAILED)
        )

        assert WrittenMetricsLog.row_under(tmp_path)["ci_indeterminada_causa"] == "comando-fallido"

    def test_an_unreadable_response_is_recorded_as_a_different_cause_than_a_failed_command(
        self, tmp_path: Path
    ) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(
            ClosedSliceMother.blocked_indeterminate_because_of(CiIndeterminateCause.UNREADABLE_RESPONSE)
        )

        assert WrittenMetricsLog.row_under(tmp_path)["ci_indeterminada_causa"] == "respuesta-no-legible"

    def test_without_a_cause_only_the_ci_field_travels_because_none_is_invented(self, tmp_path: Path) -> None:
        LocalMetricsLog(clock=self.frozen_at()).record(ClosedSliceMother.blocked_indeterminate_because_of(None))

        row = WrittenMetricsLog.row_under(tmp_path)
        assert row["ci"] == "none"
        assert "ci_indeterminada_causa" not in row


class TestTheLedgerOnlyGrows(WithTheLedgerOutOfTheRealHome):
    def test_a_second_closure_is_appended_instead_of_overwriting_the_first(self, tmp_path: Path) -> None:
        log = LocalMetricsLog(clock=self.frozen_at())

        log.record(ClosedSliceMother.closed_as(RunState.MERGED))
        log.record(ClosedSliceMother.closed_as(RunState.BLOCKED_VERIFY))

        assert [row["veredicto"] for row in WrittenMetricsLog.rows_under(tmp_path)] == ["PASA", "FALLA"]


class TestWhereTheLedgerLives:
    def test_the_directory_is_created_when_it_is_not_there_so_the_first_row_is_not_lost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "never-used-before"))

        LocalMetricsLog(clock=WithTheLedgerOutOfTheRealHome.frozen_at()).record(ClosedSliceMother.merged())

        assert (tmp_path / "never-used-before" / "slice-runner" / "metrics.jsonl").exists()
