from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.diff_stats import DiffStats
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.exceptions import UnreadableMetricsLogError
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity
from slice_runner.domain.severity_count import SeverityCount
from slice_runner.infrastructure.metrics_entry_payload import MetricsEntryPayload
from slice_runner.infrastructure.metrics_ledger_entry import MetricsLedgerEntry
from slice_runner.tests.mothers.closed_slice_mother import ClosedSliceMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.verdict_mother import FindingMother

_STAMP = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)


class TestReadingBackARowThisProgramWrote:
    def test_the_identity_of_the_slice_is_read_back_whole(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert (record.repo, record.issue, record.slice_id, record.name) == (
            ClosedSliceMother.REPO,
            ClosedSliceMother.ISSUE,
            ClosedSliceMother.SLICE_ID,
            ClosedSliceMother.NAME,
        )
        assert record.ts == _STAMP

    def test_every_closure_of_the_program_is_read_back_as_the_state_it_closed_in(self) -> None:
        for state in RunState:
            if state is RunState.OPEN:
                continue
            closed = ClosedSliceMother.closed_as(state)
            row = MetricsEntryPayload.from_domain(closed, ts=_STAMP.isoformat()).to_contract()

            record = MetricsLedgerEntry.read(row)

            assert record is not None
            assert record.state == state

    def test_the_harness_spend_measured_across_every_call_is_read_back_whole(self) -> None:
        closed = ClosedSliceMother.merged_measuring(
            HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call()
        )
        row = MetricsEntryPayload.from_domain(closed, ts=_STAMP.isoformat()).to_contract()

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.spend is not None
        measured = record.spend
        assert (measured.cost_usd, measured.turns, measured.duration_ms, measured.cache_read_tokens) == (
            closed.spend.cost_usd,
            closed.spend.turns,
            closed.spend.duration_ms,
            closed.spend.cache_read_tokens,
        )

    def test_with_nothing_measured_the_spend_is_absent_and_not_a_zero_one(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_measuring_nothing(), ts=_STAMP.isoformat()
        ).to_contract()

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.spend is None

    def test_the_diff_measured_at_the_verify_that_passed_is_read_back_whole(self) -> None:
        stats = DiffStats(files_changed=4, lines_added=51, lines_deleted=9)
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_measuring_the_diff(stats), ts=_STAMP.isoformat()
        ).to_contract()

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.diff == stats

    def test_a_closure_with_no_diff_measured_this_invocation_is_read_back_as_no_diff_at_all(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.diff is None

    def test_the_cause_of_a_discarded_verdict_is_read_back_as_the_domain_value_it_came_from(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_discarding_because_of(DiscardCause.FAILED_CALL), ts=_STAMP.isoformat()
        ).to_contract()

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.discard_cause is DiscardCause.FAILED_CALL

    def test_the_cause_ci_could_not_be_read_is_read_back_as_the_domain_value_it_came_from(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.blocked_indeterminate_because_of(CiIndeterminateCause.COMMAND_FAILED),
            ts=_STAMP.isoformat(),
        ).to_contract()

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.ci_indeterminate_cause is CiIndeterminateCause.COMMAND_FAILED

    def test_the_budgets_and_the_models_by_role_travel_untouched_as_the_raw_snapshot_they_were_written_with(
        self,
    ) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.budgets == row["budgets"]
        assert record.models_by_role == row["models_by_role"]


class TestToleratingHistory:
    def test_the_retired_label_for_a_control_block_is_still_read_as_that_state(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.closed_as(RunState.BLOCKED_CONTROLS), ts=_STAMP.isoformat()
        ).to_contract()
        row["veredicto"] = "bloqueada-puertas"

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.state is RunState.BLOCKED_CONTROLS

    def test_the_retired_key_for_control_retries_is_still_read_into_the_same_field(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        del row["reintentos_controles"]
        row["reintentos_puertas"] = 3

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.control_retries == 3

    def test_a_row_missing_a_field_added_after_it_was_written_falls_back_to_zero_instead_of_being_dropped(
        self,
    ) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        del row["debt"]

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.debt == 0

    def test_the_old_spanish_key_for_debt_is_still_read_into_the_same_field(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_leaving_out("no cubri el binario", "falta el caso de rename"),
            ts=_STAMP.isoformat(),
        ).to_contract()
        row["deuda"] = row.pop("debt")

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.debt == 2

    def test_the_old_spanish_key_for_correction_retries_is_still_read_into_the_same_field(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_after_going_back_for_every_reason(), ts=_STAMP.isoformat()
        ).to_contract()
        row["reintentos_correcciones"] = row.pop("correction_retries")

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.correction_retries == RunMother.that_went_back_for_every_reason().correction_retries

    def test_the_old_spanish_keys_for_the_findings_groups_are_still_read_into_the_same_fields(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.vetoed_over(FindingMother.without_line(severity=Severity.HIGH)),
            ts=_STAMP.isoformat(),
        ).to_contract()
        row["hallazgos"] = row.pop("findings")
        row["hallazgos_ronda_final"] = row.pop("findings_of_the_last_round")

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.findings == SeverityCount(high=1, medium=0, low=0)

    def test_the_old_spanish_keys_for_the_diff_group_are_still_read_into_the_same_fields(self) -> None:
        stats = DiffStats(files_changed=4, lines_added=51, lines_deleted=9)
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_measuring_the_diff(stats), ts=_STAMP.isoformat()
        ).to_contract()
        assert isinstance(row["diff"], dict)
        row["diff"] = {
            "ficheros": row["diff"]["files_changed"],
            "lineas_anadidas": row["diff"]["lines_added"],
            "lineas_borradas": row["diff"]["lines_deleted"],
        }

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.diff == stats

    def test_the_old_spanish_key_for_budgets_is_still_read_into_the_same_field(self) -> None:
        budgets = Budgets(slice_cost_usd=12.5, verify_retries=4)
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_with_config(budgets=budgets), ts=_STAMP.isoformat()
        ).to_contract()
        row["presupuestos"] = row.pop("budgets")

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.budgets == asdict(budgets)

    def test_the_old_spanish_key_for_models_by_role_is_still_read_into_the_same_field(self) -> None:
        models = RoleModels(understand="haiku", implement="opus")
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_with_config(models=models), ts=_STAMP.isoformat()
        ).to_contract()
        row["modelos_por_papel"] = row.pop("models_by_role")

        record = MetricsLedgerEntry.read(row)

        assert record is not None
        assert record.models_by_role == {"understand": "haiku", "implement": "opus"}

    def test_a_row_without_a_timestamp_cannot_be_placed_in_a_range_and_is_skipped(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        del row["ts"]

        assert MetricsLedgerEntry.read(row) is None

    def test_a_row_without_a_verdict_cannot_be_classified_and_is_skipped(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        del row["veredicto"]

        assert MetricsLedgerEntry.read(row) is None


class TestRejectingCorruption:
    def test_a_harness_cost_that_is_not_a_number_is_rejected_instead_of_read_back_as_zero(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_measuring(HarnessSpendMother.of_the_implementer_call()),
            ts=_STAMP.isoformat(),
        ).to_contract()
        assert isinstance(row["harness"], dict)
        row["harness"]["coste_usd"] = "free"

        with pytest.raises(UnreadableMetricsLogError):
            MetricsLedgerEntry.read(row)

    def test_a_repo_that_is_not_text_is_rejected_instead_of_read_back_as_empty(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        row["repo"] = 12345

        with pytest.raises(UnreadableMetricsLogError):
            MetricsLedgerEntry.read(row)

    def test_a_model_list_holding_a_non_string_element_is_rejected_instead_of_dropped(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_measuring(HarnessSpendMother.of_the_implementer_call()),
            ts=_STAMP.isoformat(),
        ).to_contract()
        row["modelos"] = ["sonnet", 7]

        with pytest.raises(UnreadableMetricsLogError):
            MetricsLedgerEntry.read(row)

    def test_a_verdict_outside_the_known_vocabulary_is_rejected_instead_of_skipped(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        row["veredicto"] = "en-desacuerdo"

        with pytest.raises(UnreadableMetricsLogError):
            MetricsLedgerEntry.read(row)

    def test_a_timestamp_that_is_not_iso_formatted_is_rejected_instead_of_skipped(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        row["ts"] = "not-a-timestamp"

        with pytest.raises(UnreadableMetricsLogError):
            MetricsLedgerEntry.read(row)
