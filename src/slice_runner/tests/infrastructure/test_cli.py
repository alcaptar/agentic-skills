from __future__ import annotations

import io
import json
import shutil
import sys
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.outcome import Outcome
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.infrastructure.local_skill_library import LocalSkillLibrary
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import RealExceptTheJudge, UnrunnableJudge
from slice_runner.tests.git_repo import Git
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother, JudgeVerdictMother
from slice_runner.tests.mothers.repo_mother import RepoMother
from slice_runner.tests.mothers.transition_request_mother import TransitionRequestMother

if TYPE_CHECKING:
    from pathlib import Path

_SLICE = "slice-01"

_TABLE: list[tuple[Step, Outcome, dict[str, int], tuple[Step, RunState, int]]] = [
    (Step.IMPLEMENT, Outcome.DONE, {}, (Step.RUN_CONTROLS, RunState.OPEN, 0)),
    (Step.IMPLEMENT, Outcome.OVER_BUDGET, {}, (Step.IMPLEMENT, RunState.ABORTED_BUDGET, 0)),
    (Step.RUN_CONTROLS, Outcome.DONE, {}, (Step.VERIFY, RunState.OPEN, 0)),
    (Step.RUN_CONTROLS, Outcome.FAILED, {}, (Step.IMPLEMENT, RunState.OPEN, 0)),
    (Step.RUN_CONTROLS, Outcome.FAILED, {"control_retries": 1}, (Step.IMPLEMENT, RunState.OPEN, 0)),
    (Step.RUN_CONTROLS, Outcome.FAILED, {"control_retries": 2}, (Step.RUN_CONTROLS, RunState.BLOCKED_CONTROLS, 0)),
    (Step.RUN_CONTROLS, Outcome.OVER_BUDGET, {}, (Step.RUN_CONTROLS, RunState.ABORTED_BUDGET, 0)),
    (Step.VERIFY, Outcome.DONE, {}, (Step.OPEN_PULL_REQUEST, RunState.OPEN, 0)),
    (Step.VERIFY, Outcome.DISCARDED, {}, (Step.VERIFY, RunState.OPEN, 0)),
    (Step.VERIFY, Outcome.CORRECTIONS_ORDERED, {}, (Step.IMPLEMENT, RunState.OPEN, 0)),
    (
        Step.VERIFY,
        Outcome.CORRECTIONS_ORDERED,
        {"verify_retries": 2},
        (Step.OPEN_PULL_REQUEST, RunState.OPEN, 0),
    ),
    (Step.VERIFY, Outcome.FAILED, {}, (Step.IMPLEMENT, RunState.OPEN, 0)),
    (Step.VERIFY, Outcome.FAILED, {"verify_retries": 1}, (Step.IMPLEMENT, RunState.OPEN, 0)),
    (Step.VERIFY, Outcome.FAILED, {"verify_retries": 2}, (Step.VERIFY, RunState.BLOCKED_VERIFY, 0)),
    (Step.VERIFY, Outcome.OVER_BUDGET, {}, (Step.VERIFY, RunState.ABORTED_BUDGET, 0)),
    (Step.OPEN_PULL_REQUEST, Outcome.DONE, {}, (Step.AWAIT_CI, RunState.OPEN, 0)),
    (Step.OPEN_PULL_REQUEST, Outcome.OVER_BUDGET, {}, (Step.OPEN_PULL_REQUEST, RunState.ABORTED_BUDGET, 0)),
    (Step.AWAIT_CI, Outcome.DONE, {}, (Step.AWAIT_MERGE, RunState.OPEN, 0)),
    (Step.AWAIT_CI, Outcome.PENDING, {}, (Step.AWAIT_CI, RunState.OPEN, 30)),
    (Step.AWAIT_CI, Outcome.INDETERMINATE, {}, (Step.AWAIT_CI, RunState.OPEN, 30)),
    (Step.AWAIT_CI, Outcome.INDETERMINATE, {"indeterminate_ticks": 1}, (Step.AWAIT_CI, RunState.OPEN, 30)),
    (
        Step.AWAIT_CI,
        Outcome.INDETERMINATE,
        {"indeterminate_ticks": 2},
        (Step.AWAIT_CI, RunState.BLOCKED_CI_INDETERMINATE, 0),
    ),
    (Step.AWAIT_CI, Outcome.FAILED, {}, (Step.IMPLEMENT, RunState.OPEN, 0)),
    (Step.AWAIT_CI, Outcome.FAILED, {"ci_retries": 1}, (Step.AWAIT_CI, RunState.BLOCKED_CI_RED, 0)),
    (Step.AWAIT_CI, Outcome.OVER_BUDGET, {}, (Step.AWAIT_CI, RunState.ABORTED_BUDGET, 0)),
    (Step.AWAIT_MERGE, Outcome.DONE, {}, (Step.AWAIT_MERGE, RunState.MERGED, 0)),
    (Step.AWAIT_MERGE, Outcome.PENDING, {}, (Step.AWAIT_MERGE, RunState.OPEN, 30)),
    (Step.AWAIT_MERGE, Outcome.OVER_BUDGET, {}, (Step.AWAIT_MERGE, RunState.ABORTED_BUDGET, 0)),
]

_IMPOSSIBLE: list[tuple[Step, Outcome]] = sorted(
    {(step, outcome) for step in Step for outcome in Outcome} - {(step, outcome) for step, outcome, *_ in _TABLE},
)


class BlindToTheToolboxOfThisMachine:
    @pytest.fixture(autouse=True)
    def toolbox_out_of_reach(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(LocalSkillLibrary.CONFIG_VARIABLE, str(tmp_path / "no-toolbox"))


@pytest.mark.integration
class TestTheExitCodeOfTheVerdict(BlindToTheToolboxOfThisMachine):
    def test_a_pass_exits_with_zero_and_emits_the_verdict_as_json_on_standard_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.carrying(JudgeVerdictMother.passing()))

        code = Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert code == ExitCode.OK
        assert json.loads(capsys.readouterr().out) == {"veredicto": "PASA", "hallazgos": []}

    def test_a_fail_exits_with_one_and_emits_every_finding_whoever_retries_the_slice_needs(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.recorded())

        code = Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert code == ExitCode.VETOED
        emitted = json.loads(capsys.readouterr().out)
        assert emitted["veredicto"] == "FALLA"
        assert [finding["severidad"] for finding in emitted["hallazgos"]] == ["alta", "alta", "media", "media"]


@pytest.mark.integration
class TestWhenThereIsNoVerdictToTrust(BlindToTheToolboxOfThisMachine):
    def test_an_incoherent_verdict_exits_with_two_instead_of_being_treated_as_a_pass(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        incoherent = JudgeVerdictMother.passing_with(JudgeVerdictMother.high_severity_finding(path="mod.py"))
        process = RealExceptTheJudge(HarnessEnvelopeMother.carrying(incoherent))

        code = Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert code == ExitCode.NO_USABLE_VERDICT
        output = capsys.readouterr()
        assert output.out == ""
        assert "PASA with 1 finding" in output.err

    def test_a_judge_that_cannot_be_launched_exits_with_two_instead_of_with_the_code_of_the_veto(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        code = Cli(process=UnrunnableJudge()).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert code == ExitCode.NO_USABLE_VERDICT
        output = capsys.readouterr()
        assert output.out == ""
        assert "claude" in output.err


@pytest.mark.integration
class TestWhenThereIsNothingToJudge(BlindToTheToolboxOfThisMachine):
    @pytest.fixture
    def process(self) -> RealExceptTheJudge:
        return RealExceptTheJudge(HarnessEnvelopeMother.carrying(JudgeVerdictMother.passing()))

    def test_with_nothing_staged_it_exits_with_three_without_spending_an_invocation_of_the_judge(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], process: RealExceptTheJudge
    ) -> None:
        repo = RepoMother.with_nothing_staged(tmp_path)

        code = Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert code == ExitCode.NO_DIFF
        assert process.calls == 0
        assert "staged" in capsys.readouterr().err

    def test_a_base_that_does_not_resolve_does_not_exit_with_the_code_of_the_empty_index(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], process: RealExceptTheJudge
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        code = Cli(process=process).verify(repo=str(repo), base="does-not-exist", slice_id=_SLICE)

        assert code == ExitCode.USAGE_ERROR
        assert process.calls == 0
        assert "does-not-exist" in capsys.readouterr().err

    def test_a_repo_that_does_not_resolve_exits_with_four_without_blaming_the_base(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], process: RealExceptTheJudge
    ) -> None:
        code = Cli(process=process).verify(
            repo=str(RepoMother.outside_git(tmp_path)), base=Git.BASE_BRANCH, slice_id=_SLICE
        )

        assert code == ExitCode.USAGE_ERROR
        assert process.calls == 0
        assert "the repo or the base" in capsys.readouterr().err


@pytest.mark.integration
class TestTheDiffTheJudgeReads(BlindToTheToolboxOfThisMachine):
    def test_the_judge_is_handed_the_diff_of_the_index_inside_the_prompt(self, tmp_path: Path) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.recorded())

        Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert "+    return 2" in process.stdin

    def test_no_path_to_a_materialised_patch_travels_because_there_is_no_patch_to_point_at(
        self, tmp_path: Path
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.recorded())

        Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert "slice.diff" not in process.stdin


@pytest.mark.integration
class TestWhatTheJudgeWasDeniedReading(BlindToTheToolboxOfThisMachine):
    def test_a_denied_read_is_warned_about_on_standard_error_because_the_yardstick_may_be_incomplete(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.denying_a_read())

        code = Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        output = capsys.readouterr()
        assert code == ExitCode.OK
        assert HarnessEnvelopeMother.DENIED_READ in output.err
        assert json.loads(output.out) == {"veredicto": "PASA", "hallazgos": []}

    def test_a_run_with_nothing_denied_says_nothing_so_the_warning_keeps_meaning_something(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.carrying(JudgeVerdictMother.passing()))

        Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert capsys.readouterr().err == ""


@pytest.mark.integration
class TestWhatTheJudgeMayRead:
    def test_the_toolbox_of_the_machine_is_granted_next_to_the_repo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        toolbox = tmp_path / "toolbox"
        (toolbox / "skills").mkdir(parents=True)
        monkeypatch.setenv(LocalSkillLibrary.CONFIG_VARIABLE, str(toolbox))
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.recorded())

        Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert Argv(process.argv).values_of("--add-dir") == [str(repo), str(toolbox / "skills")]

    def test_what_the_judge_may_read_is_told_to_the_judge_and_not_only_granted_in_the_argv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        toolbox = tmp_path / "toolbox"
        (toolbox / "skills").mkdir(parents=True)
        monkeypatch.setenv(LocalSkillLibrary.CONFIG_VARIABLE, str(toolbox))
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.recorded())

        Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert str(toolbox / "skills") in process.stdin


@pytest.mark.integration
class TestTheEntrypoint(BlindToTheToolboxOfThisMachine):
    @pytest.fixture(autouse=True)
    def judge_out_of_reach(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        toolbox = tmp_path / "only-git"
        toolbox.mkdir()
        (toolbox / "git").symlink_to(shutil.which("git") or "/usr/bin/git")
        monkeypatch.setenv("PATH", str(toolbox))

    def test_main_wires_the_parsed_arguments_into_the_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_nothing_staged(tmp_path)

        code = Cli.main(["verify", "--repo", str(repo), "--base", Git.BASE_BRANCH, "--slice", _SLICE])

        assert code == ExitCode.NO_DIFF
        assert "staged" in capsys.readouterr().err

    def test_main_reports_the_base_it_was_given_and_not_a_guessed_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        code = Cli.main(["verify", "--repo", str(repo), "--base", "a-base-that-is-not-there", "--slice", _SLICE])

        assert code == ExitCode.USAGE_ERROR
        assert "a-base-that-is-not-there" in capsys.readouterr().err


class TestTheTransitionOfEveryPair:
    @pytest.mark.parametrize(("step", "outcome", "spent", "expected"), _TABLE)
    def test_every_pair_of_step_and_outcome_has_one_answer_and_this_is_it(
        self,
        step: Step,
        outcome: Outcome,
        spent: dict[str, int],
        expected: tuple[Step, RunState, int],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        code = Cli.explain(request=TransitionRequestMother.asking(step, outcome, **spent))

        assert code == ExitCode.OK
        emitted = json.loads(capsys.readouterr().out)
        assert (emitted["run"]["step"], emitted["state"], emitted["wait_seconds"]) == expected

    def test_the_whole_run_travels_in_the_transition_so_nobody_downstream_recounts_it(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.RUN_CONTROLS, Outcome.FAILED, verify_discards=1)

        Cli.explain(request=asked)

        assert json.loads(capsys.readouterr().out) == {
            "run": {
                "step": "implement",
                "control_retries": 1,
                "verify_retries": 0,
                "ci_retries": 0,
                "indeterminate_ticks": 0,
                "verify_discards": 1,
            },
            "state": "open",
            "wait_seconds": 0,
        }


class TestWhatEachBudgetPays:
    def test_a_red_control_spends_a_retry_of_its_own_and_not_one_of_the_judge(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Cli.explain(request=TransitionRequestMother.asking(Step.RUN_CONTROLS, Outcome.FAILED))

        spent = json.loads(capsys.readouterr().out)["run"]
        assert (spent["control_retries"], spent["verify_retries"]) == (1, 0)

    def test_a_veto_spends_a_retry_of_the_judge_and_not_one_of_the_controls(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Cli.explain(request=TransitionRequestMother.asking(Step.VERIFY, Outcome.FAILED))

        spent = json.loads(capsys.readouterr().out)["run"]
        assert (spent["verify_retries"], spent["control_retries"]) == (1, 0)

    def test_a_discarded_verdict_is_counted_apart_because_the_code_was_never_touched(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Cli.explain(request=TransitionRequestMother.asking(Step.VERIFY, Outcome.DISCARDED, verify_retries=2))

        emitted = json.loads(capsys.readouterr().out)
        assert emitted["state"] == RunState.OPEN
        assert (emitted["run"]["verify_discards"], emitted["run"]["verify_retries"]) == (1, 2)

    def test_a_round_of_corrections_spends_the_same_budget_as_a_veto_and_not_one_of_its_own(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.VERIFY, Outcome.CORRECTIONS_ORDERED, verify_retries=1)

        Cli.explain(request=asked)

        assert json.loads(capsys.readouterr().out)["run"]["verify_retries"] == 2

    def test_the_last_corrections_become_debt_instead_of_blocking_a_slice_the_judge_did_not_veto(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.VERIFY, Outcome.CORRECTIONS_ORDERED, verify_retries=2)

        Cli.explain(request=asked)

        emitted = json.loads(capsys.readouterr().out)
        assert (emitted["run"]["step"], emitted["state"]) == (Step.OPEN_PULL_REQUEST, RunState.OPEN)

    def test_an_answer_from_the_ci_clears_the_ticks_that_had_none_because_the_window_wants_them_consecutive(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.AWAIT_CI, Outcome.PENDING, indeterminate_ticks=2)

        Cli.explain(request=asked)

        assert json.loads(capsys.readouterr().out)["run"]["indeterminate_ticks"] == 0


class TestWhenThereIsNoTransitionToExplain:
    @pytest.mark.parametrize(("step", "outcome"), _IMPOSSIBLE)
    def test_a_pair_the_prose_never_describes_is_refused_instead_of_taking_a_generic_branch(
        self, step: Step, outcome: Outcome, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.explain(request=TransitionRequestMother.asking(step, outcome))

        assert code == ExitCode.USAGE_ERROR
        output = capsys.readouterr()
        assert output.out == ""
        assert f"`{step}`" in output.err
        assert f"`{outcome}`" in output.err

    def test_a_run_that_is_not_json_is_refused_because_a_guessed_one_advances_the_wrong_slice(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.explain(request=TransitionRequestMother.not_even_json())

        assert code == ExitCode.USAGE_ERROR
        assert capsys.readouterr().out == ""

    def test_a_step_nobody_declared_is_refused_instead_of_defaulting_to_the_first_one(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.explain(request=TransitionRequestMother.with_a_step_nobody_declared())

        assert code == ExitCode.USAGE_ERROR
        assert "deploy" in capsys.readouterr().err

    def test_a_counter_that_arrives_as_text_is_refused_because_it_decides_when_a_budget_runs_out(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.explain(request=TransitionRequestMother.with_a_counter_that_arrives_as_text())

        assert code == ExitCode.USAGE_ERROR
        assert "control_retries" in capsys.readouterr().err


class TestTheDocumentedCommand:
    def test_it_parses_with_the_repo_the_base_and_the_slice(self) -> None:
        arguments = Cli.parser().parse_args(
            ["verify", "--repo", "/repos/project", "--base", "master", "--slice", _SLICE]
        )

        assert (arguments.repo, arguments.base, arguments.slice_id) == ("/repos/project", "master", _SLICE)

    def test_the_base_has_no_default_value_because_a_guessed_one_diffs_the_wrong_range(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(["verify", "--repo", "/repos/project", "--slice", _SLICE])

        assert "the following arguments are required: --base" in capsys.readouterr().err

    def test_the_slice_has_no_default_value_because_a_guessed_one_files_the_pair_under_the_wrong_slice(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(["verify", "--repo", "/repos/project", "--base", "master"])

        assert "the following arguments are required: --slice" in capsys.readouterr().err

    def test_explain_takes_the_run_on_standard_input_and_not_as_a_flag(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.IMPLEMENT, Outcome.DONE)
        monkeypatch.setattr(sys, "stdin", io.StringIO(asked))

        code = Cli.main(["explain"])

        assert code == ExitCode.OK
        assert json.loads(capsys.readouterr().out)["run"]["step"] == Step.RUN_CONTROLS
