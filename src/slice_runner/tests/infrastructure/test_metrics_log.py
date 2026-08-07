from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.exceptions import RunNotClosedError
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.metrics_invocation import MetricsInvocation
from slice_runner.infrastructure.metrics_script_log import MetricsNotRecordedError, MetricsScriptLog
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import ProcessDoubles
from slice_runner.tests.mothers.closed_slice_mother import ClosedSliceMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.verdict_mother import FindingMother

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.closed_slice import ClosedSlice


class TheRecord:
    @staticmethod
    def of(closed: ClosedSlice) -> Argv:
        return Argv(MetricsInvocation(closed=closed).argv)


class TestWhereTheDurableLogIsWrittenFrom:
    def test_the_script_ships_with_the_program_so_it_never_drifts_from_what_the_program_sends(self) -> None:
        script = MetricsInvocation(closed=ClosedSliceMother.merged()).script

        assert script.exists()
        assert script == MetricsInvocation.PROGRAM_ROOT / "skills" / "slice-runner" / "scripts" / "metrics.py"

    def test_the_toolbox_configuration_cannot_move_it_because_a_symlink_may_point_anywhere(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        assert tmp_path not in MetricsInvocation(closed=ClosedSliceMother.merged()).script.parents

    def test_it_is_not_looked_up_inside_the_repo_of_the_slice_because_it_may_live_in_another_one(self) -> None:
        closed = ClosedSliceMother.merged()

        assert closed.repo not in str(MetricsInvocation(closed=closed).script)

    def test_the_log_is_written_by_the_script_and_not_by_the_program_itself(self) -> None:
        argv = TheRecord.of(ClosedSliceMother.merged())

        assert argv.executable == "python3"
        assert argv.contains("record")


class TestHowEachClosureIsRecorded:
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
        self, state: RunState, verdict: str, ci: str
    ) -> None:
        argv = TheRecord.of(ClosedSliceMother.closed_as(state))

        assert (argv.value_of("--veredicto"), argv.value_of("--ci")) == (verdict, ci)

    def test_a_run_that_has_not_closed_is_rejected_instead_of_written_as_a_row(self) -> None:
        with pytest.raises(RunNotClosedError, match="one line per closed slice"):
            TheRecord.of(ClosedSliceMother.still_open())

    def test_the_slice_travels_by_the_three_names_the_log_indexes_it_with(self) -> None:
        argv = TheRecord.of(ClosedSliceMother.merged())

        assert (argv.value_of("--repo"), argv.value_of("--slice"), argv.value_of("--name")) == (
            ClosedSliceMother.REPO,
            ClosedSliceMother.SLICE_ID,
            ClosedSliceMother.NAME,
        )


class TestWhatOfTheHarnessIsWritten:
    def test_the_spend_of_every_call_of_the_slice_travels_summed_and_not_only_the_last_one(self) -> None:
        closed = ClosedSliceMother.merged_measuring(
            HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call()
        )

        argv = TheRecord.of(closed)

        assert argv.value_of("--coste-usd") == "0.3951979"
        assert argv.value_of("--turnos") == "14"
        assert argv.value_of("--duracion-ms") == "65652"

    def test_with_nothing_measured_no_number_of_the_harness_is_written(self) -> None:
        argv = TheRecord.of(ClosedSliceMother.merged_measuring_nothing())

        assert [flag for flag in ("--coste-usd", "--turnos", "--duracion-ms") if argv.contains(flag)] == []

    def test_the_wall_clock_duration_is_never_written_because_nothing_here_measures_it(self) -> None:
        argv = TheRecord.of(ClosedSliceMother.merged_measuring(HarnessSpendMother.of_the_judge_call()))

        assert not argv.contains("--duracion-s")

    def test_the_token_count_is_never_written_either_because_the_envelope_does_not_bring_it(self) -> None:
        argv = TheRecord.of(ClosedSliceMother.merged_measuring(HarnessSpendMother.of_the_judge_call()))

        assert not argv.contains("--coste-tokens")

    def test_the_cache_read_tokens_travel_next_to_the_rest_of_what_the_harness_measured(self) -> None:
        argv = TheRecord.of(ClosedSliceMother.merged_measuring(HarnessSpendMother.of_the_judge_call()))

        assert argv.value_of("--tokens-cache") == "15510"

    def test_the_model_the_harness_declares_travels_and_not_the_alias_the_program_requested(self) -> None:
        argv = TheRecord.of(ClosedSliceMother.merged_measuring(HarnessSpendMother.of_the_implementer_call()))

        assert argv.values_of("--modelo") == ["claude-sonnet-5"]

    def test_a_slice_that_used_more_than_one_model_writes_every_one_of_them(self) -> None:
        argv = TheRecord.of(
            ClosedSliceMother.merged_measuring(
                HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call()
            )
        )

        assert argv.values_of("--modelo") == ["claude-haiku-4-5-20251001", "claude-sonnet-5"]

    def test_with_nothing_measured_no_model_or_cache_figure_is_written(self) -> None:
        argv = TheRecord.of(ClosedSliceMother.merged_measuring_nothing())

        assert [flag for flag in ("--modelo", "--tokens-cache") if argv.contains(flag)] == []


class TestWhatVariantIsWritten:
    def test_every_record_the_program_builds_names_the_variant_that_is_conducting_the_slice(self) -> None:
        argv = TheRecord.of(ClosedSliceMother.merged())

        assert argv.value_of("--variante") == MetricsInvocation.VARIANT


class TestWhatTheRunAlreadyCounted:
    def test_the_retries_of_implementing_are_the_sum_of_the_four_ways_back_to_that_step(self) -> None:
        run = RunMother.that_went_back_for_every_reason()

        argv = TheRecord.of(ClosedSliceMother.merged_after_going_back_for_every_reason())

        assert argv.value_of("--reintentos-implement") == str(
            run.control_retries + run.hygiene_retries + run.verify_retries + run.ci_retries
        )

    def test_each_kind_of_retry_also_travels_on_its_own_so_the_sum_can_be_read_apart(self) -> None:
        run = RunMother.that_went_back_for_every_reason()

        argv = TheRecord.of(ClosedSliceMother.merged_after_going_back_for_every_reason())

        assert (
            argv.value_of("--reintentos-controles"),
            argv.value_of("--reintentos-verify"),
            argv.value_of("--reintentos-ci"),
        ) == (str(run.control_retries), str(run.verify_retries), str(run.ci_retries))

    def test_the_findings_travel_counted_by_severity_and_not_as_a_single_total(self) -> None:
        argv = TheRecord.of(
            ClosedSliceMother.vetoed_over(
                FindingMother.without_line(severity=Severity.HIGH),
                FindingMother.without_line(severity=Severity.LOW),
                FindingMother.without_line(severity=Severity.LOW),
            )
        )

        assert (
            argv.value_of("--hallazgos-alta"),
            argv.value_of("--hallazgos-media"),
            argv.value_of("--hallazgos-baja"),
        ) == ("1", "0", "2")

    def test_the_findings_of_the_last_round_travel_apart_so_a_pass_with_one_accumulated_is_never_ambiguous(
        self,
    ) -> None:
        argv = TheRecord.of(
            ClosedSliceMother.merged_after_correcting(FindingMother.without_line(severity=Severity.HIGH))
        )

        assert (
            argv.value_of("--hallazgos-alta"),
            argv.value_of("--hallazgos-ronda-final-alta"),
            argv.value_of("--hallazgos-ronda-final-media"),
            argv.value_of("--hallazgos-ronda-final-baja"),
        ) == ("1", "0", "0", "0")


class TestWhyTheJudgeWasReinvoked:
    def test_the_cause_of_the_discards_travels_next_to_their_count(self) -> None:
        run = RunMother.that_went_back_for_every_reason()

        argv = TheRecord.of(ClosedSliceMother.merged_discarding_because_of(DiscardCause.FAILED_CALL))

        assert (argv.value_of("--descartes-verify"), argv.value_of("--descartes-verify-causa")) == (
            str(run.verify_discards),
            "llamada-fallida",
        )

    def test_an_incoherent_verdict_is_recorded_as_a_different_cause_than_a_call_that_never_answered(self) -> None:
        argv = TheRecord.of(ClosedSliceMother.merged_discarding_because_of(DiscardCause.INCOHERENT_VERDICT))

        assert argv.value_of("--descartes-verify-causa") == "veredicto-incoherente"

    def test_without_a_cause_only_the_count_travels_because_none_is_invented(self) -> None:
        argv = TheRecord.of(ClosedSliceMother.merged_discarding_because_of(None))

        assert argv.contains("--descartes-verify")
        assert not argv.contains("--descartes-verify-causa")


class TestWhenTheScriptDoesNotWrite:
    def test_the_record_is_handed_to_the_script_exactly_once(self) -> None:
        process = ProcessDoubles.exiting(code=0)

        MetricsScriptLog(process=process).record(ClosedSliceMother.merged())

        assert process.run.call_count == 1

    def test_a_non_zero_exit_is_reported_with_what_the_script_left_on_standard_error(self) -> None:
        process = ProcessDoubles.exiting(code=2, stderr="metrics.py: error: unrecognized arguments: --turnos")

        with pytest.raises(MetricsNotRecordedError, match="unrecognized arguments"):
            MetricsScriptLog(process=process).record(ClosedSliceMother.merged())

    def test_the_slice_that_went_unmeasured_is_named_in_the_error(self) -> None:
        process = ProcessDoubles.exiting(code=1, stderr="boom")

        with pytest.raises(MetricsNotRecordedError, match=ClosedSliceMother.SLICE_ID):
            MetricsScriptLog(process=process).record(ClosedSliceMother.merged())
