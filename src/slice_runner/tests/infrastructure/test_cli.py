from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.call_trace import HarnessCall
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.local_call_spend_log import LocalCallSpendLog
from slice_runner.infrastructure.local_call_trace import LocalCallTrace
from slice_runner.infrastructure.system_clock import SystemClock
from slice_runner.infrastructure.understanding_invocation import UnderstandingInvocation
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import Answer, RealExceptTheJudge, TimingOutProcess, UnrunnableJudge
from slice_runner.tests.git_repo import Git
from slice_runner.tests.mothers.conversation_transcript_mother import ConversationTranscriptMother
from slice_runner.tests.mothers.gh_conversation_mother import GhConversationMother
from slice_runner.tests.mothers.harness_call_spend_mother import HarnessCallSpendMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother, JudgeVerdictMother
from slice_runner.tests.mothers.repo_mother import RepoMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.transition_request_mother import TransitionRequestMother
from slice_runner.tests.run_invocation import RunInvocation

if TYPE_CHECKING:
    from slice_runner.domain.call_spend_log import HarnessCallSpend

_SLICE = "slice-01"
_IMPLEMENTER_PAYLOAD = "implementer-two-paths"

_TABLE: list[tuple[Step, Outcome, dict[str, int], tuple[Step, RunState, int]]] = [
    (Step.UNDERSTAND, Outcome.DONE, {}, (Step.IMPLEMENT, RunState.OPEN, 0)),
    (Step.UNDERSTAND, Outcome.PENDING, {}, (Step.UNDERSTAND, RunState.OPEN, 30)),
    (Step.UNDERSTAND, Outcome.OVER_BUDGET, {}, (Step.UNDERSTAND, RunState.ABORTED_BUDGET, 0)),
    (Step.IMPLEMENT, Outcome.DONE, {}, (Step.RUN_CONTROLS, RunState.OPEN, 0)),
    (Step.IMPLEMENT, Outcome.OVER_BUDGET, {}, (Step.IMPLEMENT, RunState.ABORTED_BUDGET, 0)),
    (Step.RUN_CONTROLS, Outcome.DONE, {}, (Step.VERIFY, RunState.OPEN, 0)),
    (Step.RUN_CONTROLS, Outcome.FAILED, {}, (Step.IMPLEMENT, RunState.OPEN, 0)),
    (Step.RUN_CONTROLS, Outcome.FAILED, {"control_retries": 1}, (Step.IMPLEMENT, RunState.OPEN, 0)),
    (Step.RUN_CONTROLS, Outcome.FAILED, {"control_retries": 2}, (Step.RUN_CONTROLS, RunState.BLOCKED_CONTROLS, 0)),
    (Step.RUN_CONTROLS, Outcome.HYGIENE_REJECTED, {}, (Step.IMPLEMENT, RunState.OPEN, 0)),
    (Step.RUN_CONTROLS, Outcome.HYGIENE_REJECTED, {"hygiene_retries": 1}, (Step.IMPLEMENT, RunState.OPEN, 0)),
    (
        Step.RUN_CONTROLS,
        Outcome.HYGIENE_REJECTED,
        {"hygiene_retries": 2},
        (Step.RUN_CONTROLS, RunState.BLOCKED_HYGIENE, 0),
    ),
    (Step.RUN_CONTROLS, Outcome.INDETERMINATE, {}, (Step.RUN_CONTROLS, RunState.OPEN, 30)),
    (Step.RUN_CONTROLS, Outcome.INDETERMINATE, {"control_retries": 2}, (Step.RUN_CONTROLS, RunState.OPEN, 30)),
    (Step.RUN_CONTROLS, Outcome.OVER_BUDGET, {}, (Step.RUN_CONTROLS, RunState.ABORTED_BUDGET, 0)),
    (Step.VERIFY, Outcome.DONE, {}, (Step.OPEN_PULL_REQUEST, RunState.OPEN, 0)),
    (Step.VERIFY, Outcome.DISCARDED, {}, (Step.VERIFY, RunState.OPEN, 0)),
    (Step.VERIFY, Outcome.CORRECTIONS_ORDERED, {}, (Step.IMPLEMENT, RunState.OPEN, 0)),
    (
        Step.VERIFY,
        Outcome.CORRECTIONS_ORDERED,
        {"correction_retries": 2},
        (Step.OPEN_PULL_REQUEST, RunState.OPEN, 0),
    ),
    (
        Step.VERIFY,
        Outcome.CORRECTIONS_ORDERED,
        {"verify_retries": 2},
        (Step.IMPLEMENT, RunState.OPEN, 0),
    ),
    (Step.VERIFY, Outcome.FAILED, {}, (Step.IMPLEMENT, RunState.OPEN, 0)),
    (Step.VERIFY, Outcome.FAILED, {"verify_retries": 1}, (Step.IMPLEMENT, RunState.OPEN, 0)),
    (Step.VERIFY, Outcome.FAILED, {"verify_retries": 2}, (Step.VERIFY, RunState.BLOCKED_VERIFY, 0)),
    (
        Step.VERIFY,
        Outcome.FAILED,
        {"correction_retries": 2},
        (Step.IMPLEMENT, RunState.OPEN, 0),
    ),
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


@pytest.fixture(autouse=True)
def _every_run_closes_its_metrics_row_outside_the_real_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "durable-metrics"))


class BlindToTheToolboxOfThisMachine:
    @pytest.fixture(autouse=True)
    def toolbox_out_of_reach(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "no-toolbox"))


class ReadingWhatWasReported:
    @staticmethod
    def _reported(capsys: pytest.CaptureFixture[str]) -> str:
        output = capsys.readouterr()
        assert output.out == ""

        return output.err


@pytest.mark.integration
class TestTheExitCodeOfTheVerdict(BlindToTheToolboxOfThisMachine):
    def test_a_pass_exits_with_zero_and_emits_the_verdict_as_json_on_standard_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.carrying(JudgeVerdictMother.passing()))

        code = Cli(process=process, budgets=Budgets()).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert code == ExitCode.OK
        assert json.loads(capsys.readouterr().out) == {"veredicto": "PASA", "hallazgos": []}

    def test_a_fail_exits_with_one_and_emits_every_finding_whoever_retries_the_slice_needs(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.recorded())

        code = Cli(process=process, budgets=Budgets()).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

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

        code = Cli(process=process, budgets=Budgets()).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert code == ExitCode.NO_USABLE_VERDICT
        output = capsys.readouterr()
        assert output.out == ""
        assert "PASA with 1 finding" in output.err

    def test_a_judge_that_cannot_be_launched_exits_with_two_instead_of_with_the_code_of_the_veto(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        code = Cli(process=UnrunnableJudge(), budgets=Budgets()).verify(
            repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE
        )

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

        code = Cli(process=process, budgets=Budgets()).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert code == ExitCode.NO_DIFF
        assert process.calls == 0
        assert "staged" in capsys.readouterr().err

    def test_a_base_that_does_not_resolve_does_not_exit_with_the_code_of_the_empty_index(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], process: RealExceptTheJudge
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        code = Cli(process=process, budgets=Budgets()).verify(repo=str(repo), base="does-not-exist", slice_id=_SLICE)

        assert code == ExitCode.USAGE_ERROR
        assert process.calls == 0
        assert "does-not-exist" in capsys.readouterr().err

    def test_a_repo_that_does_not_resolve_exits_with_four_without_blaming_the_base(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], process: RealExceptTheJudge
    ) -> None:
        code = Cli(process=process, budgets=Budgets()).verify(
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

        Cli(process=process, budgets=Budgets()).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert "+    return 2" in process.stdin

    def test_no_path_to_a_materialised_patch_travels_because_there_is_no_patch_to_point_at(
        self, tmp_path: Path
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.recorded())

        Cli(process=process, budgets=Budgets()).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert "slice.diff" not in process.stdin


@pytest.mark.integration
class TestWhatTheJudgeWasDeniedReading(BlindToTheToolboxOfThisMachine):
    def test_a_denied_read_is_warned_about_on_standard_error_because_the_yardstick_may_be_incomplete(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.denying_a_read())

        code = Cli(process=process, budgets=Budgets()).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        output = capsys.readouterr()
        assert code == ExitCode.OK
        assert HarnessEnvelopeMother.DENIED_READ in output.err
        assert json.loads(output.out) == {"veredicto": "PASA", "hallazgos": []}

    def test_a_run_with_nothing_denied_says_nothing_so_the_warning_keeps_meaning_something(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.carrying(JudgeVerdictMother.passing()))

        Cli(process=process, budgets=Budgets()).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert capsys.readouterr().err == ""


@pytest.mark.integration
class TestWhatTheJudgeMayRead:
    def test_the_toolbox_of_the_machine_is_granted_next_to_the_repo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        toolbox = tmp_path / "toolbox"
        (toolbox / "skills").mkdir(parents=True)
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(toolbox))
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.recorded())

        Cli(process=process, budgets=Budgets()).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

        assert Argv(process.argv).values_of("--add-dir") == [str(repo), str(toolbox / "skills")]

    def test_what_the_judge_may_read_is_told_to_the_judge_and_not_only_granted_in_the_argv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        toolbox = tmp_path / "toolbox"
        (toolbox / "skills").mkdir(parents=True)
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(toolbox))
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.recorded())

        Cli(process=process, budgets=Budgets()).verify(repo=str(repo), base=Git.BASE_BRANCH, slice_id=_SLICE)

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


class TestTheCommandThatPrintsAConversation:
    _REPO = "alcaptar/agentic-skills"
    _ISSUE = 45
    _SLICE = "slice-05"
    _WORKTREE = "/Users/someone/repos/the-slice"

    @pytest.fixture(autouse=True)
    def toolbox(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

    def _traced(self) -> None:
        LocalCallTrace(clock=SystemClock()).record(
            HarnessCall(
                repo=self._REPO,
                issue=self._ISSUE,
                slice_id=self._SLICE,
                step=Step.IMPLEMENT,
                session=ConversationTranscriptMother.SESSION,
            )
        )
        ConversationTranscriptMother.written_under(ClaudeConfig.root(), repo=self._WORKTREE)

    def test_the_conversation_of_a_traced_call_is_printed_as_readable_text(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._traced()

        code = Cli.read(
            repo=self._REPO, issue=self._ISSUE, worktree=self._WORKTREE, slice_id=self._SLICE, step=Step.IMPLEMENT
        )

        assert code == ExitCode.OK
        output = capsys.readouterr()
        assert output.err == ""
        assert "Now let's confirm RED before implementing:" in output.out

    def test_a_slice_and_step_never_traced_exits_with_a_usage_error_instead_of_guessing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.read(
            repo=self._REPO, issue=self._ISSUE, worktree=self._WORKTREE, slice_id=self._SLICE, step=Step.IMPLEMENT
        )

        assert code == ExitCode.USAGE_ERROR
        output = capsys.readouterr()
        assert output.out == ""
        assert self._SLICE in output.err

    def test_a_traced_session_whose_conversation_was_never_kept_exits_with_a_usage_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        LocalCallTrace(clock=SystemClock()).record(
            HarnessCall(
                repo=self._REPO,
                issue=self._ISSUE,
                slice_id=self._SLICE,
                step=Step.IMPLEMENT,
                session=ConversationTranscriptMother.SESSION,
            )
        )

        code = Cli.read(
            repo=self._REPO, issue=self._ISSUE, worktree=self._WORKTREE, slice_id=self._SLICE, step=Step.IMPLEMENT
        )

        assert code == ExitCode.USAGE_ERROR
        assert ConversationTranscriptMother.SESSION in capsys.readouterr().err

    def test_main_wires_the_parsed_arguments_into_the_read(self, capsys: pytest.CaptureFixture[str]) -> None:
        self._traced()

        code = Cli.main(
            [
                "read",
                "--repo",
                self._REPO,
                "--issue",
                str(self._ISSUE),
                "--worktree",
                self._WORKTREE,
                "--slice",
                self._SLICE,
                "--step",
                str(Step.IMPLEMENT),
            ]
        )

        assert code == ExitCode.OK
        assert "Now let's confirm RED before implementing:" in capsys.readouterr().out

    def test_the_step_has_no_default_because_a_guessed_one_reads_the_wrong_call(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(
                [
                    "read",
                    "--repo",
                    self._REPO,
                    "--issue",
                    str(self._ISSUE),
                    "--worktree",
                    self._WORKTREE,
                    "--slice",
                    self._SLICE,
                ]
            )

        assert "the following arguments are required: --step" in capsys.readouterr().err

    def test_a_step_nobody_declared_is_refused_instead_of_being_forwarded(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(
                [
                    "read",
                    "--repo",
                    self._REPO,
                    "--issue",
                    str(self._ISSUE),
                    "--worktree",
                    self._WORKTREE,
                    "--slice",
                    self._SLICE,
                    "--step",
                    "deploy",
                ]
            )

        assert "invalid choice" in capsys.readouterr().err


class TestTheCommandThatSumsSpendByRole:
    _REPO = "alcaptar/agentic-skills"
    _ISSUE = 45
    _SLICE = "slice-05"

    @pytest.fixture(autouse=True)
    def toolbox(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

    def _traced_and_spent(self, *, step: Step, call: HarnessCallSpend) -> None:
        LocalCallTrace(clock=SystemClock()).record(
            HarnessCall(repo=self._REPO, issue=self._ISSUE, slice_id=self._SLICE, step=step, session=call.session)
        )
        LocalCallSpendLog(clock=SystemClock()).record(call)

    def test_the_spend_of_a_traced_call_is_printed_as_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        self._traced_and_spent(step=Step.IMPLEMENT, call=HarnessCallSpendMother.of_the_implementer())

        code = Cli.spend(repo=self._REPO, issue=self._ISSUE, slice_id=self._SLICE, step=Step.IMPLEMENT)

        assert code == ExitCode.OK
        printed = json.loads(capsys.readouterr().out)
        assert printed["cost_usd"] == pytest.approx(HarnessSpendMother.of_the_implementer_call().cost_usd)
        assert printed["calls"] == 1

    def test_a_slice_and_step_never_traced_prints_nothing_measured_instead_of_failing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.spend(repo=self._REPO, issue=self._ISSUE, slice_id=self._SLICE, step=Step.IMPLEMENT)

        assert code == ExitCode.OK
        assert json.loads(capsys.readouterr().out)["calls"] == 0

    def test_main_wires_the_parsed_arguments_into_spend(self, capsys: pytest.CaptureFixture[str]) -> None:
        self._traced_and_spent(step=Step.IMPLEMENT, call=HarnessCallSpendMother.of_the_implementer())

        code = Cli.main(
            [
                "spend",
                "--repo",
                self._REPO,
                "--issue",
                str(self._ISSUE),
                "--slice",
                self._SLICE,
                "--step",
                str(Step.IMPLEMENT),
            ]
        )

        assert code == ExitCode.OK
        printed = json.loads(capsys.readouterr().out)
        assert printed["cost_usd"] == pytest.approx(HarnessSpendMother.of_the_implementer_call().cost_usd)

    def test_the_split_between_implementing_and_judging_is_answered_by_two_calls_with_no_subtraction_by_hand(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._traced_and_spent(step=Step.IMPLEMENT, call=HarnessCallSpendMother.of_the_implementer())
        self._traced_and_spent(step=Step.VERIFY, call=HarnessCallSpendMother.of_the_judge())

        implementer_code = Cli.spend(repo=self._REPO, issue=self._ISSUE, slice_id=self._SLICE, step=Step.IMPLEMENT)
        implementer_cost = json.loads(capsys.readouterr().out)["cost_usd"]
        judge_code = Cli.spend(repo=self._REPO, issue=self._ISSUE, slice_id=self._SLICE, step=Step.VERIFY)
        judge_cost = json.loads(capsys.readouterr().out)["cost_usd"]

        assert implementer_code == ExitCode.OK
        assert judge_code == ExitCode.OK
        assert implementer_cost == pytest.approx(HarnessSpendMother.of_the_implementer_call().cost_usd)
        assert judge_cost == pytest.approx(HarnessSpendMother.of_the_judge_call().cost_usd)

    def test_the_slice_has_no_default_because_a_guessed_one_sums_the_wrong_calls(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(
                ["spend", "--repo", "alcaptar/agentic-skills", "--issue", "45", "--step", str(Step.IMPLEMENT)]
            )

        assert "the following arguments are required: --slice" in capsys.readouterr().err

    def test_a_step_nobody_declared_is_refused_instead_of_being_forwarded(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(["spend", "--slice", self._SLICE, "--step", "deploy"])

        assert "invalid choice" in capsys.readouterr().err


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
        code = Cli.explain(request=TransitionRequestMother.asking(step, outcome, **spent), budgets=Budgets())

        assert code == ExitCode.OK
        emitted = json.loads(capsys.readouterr().out)
        assert (emitted["run"]["step"], emitted["state"], emitted["wait_seconds"]) == expected

    def test_the_whole_run_travels_in_the_transition_so_nobody_downstream_recounts_it(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.RUN_CONTROLS, Outcome.FAILED, verify_discards=1)

        Cli.explain(request=asked, budgets=Budgets())

        assert json.loads(capsys.readouterr().out) == {
            "run": {
                "step": "implement",
                "corrected": "",
                "control_retries": 1,
                "hygiene_retries": 0,
                "verify_retries": 0,
                "correction_retries": 0,
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
        Cli.explain(request=TransitionRequestMother.asking(Step.RUN_CONTROLS, Outcome.FAILED), budgets=Budgets())

        spent = json.loads(capsys.readouterr().out)["run"]
        assert (spent["control_retries"], spent["verify_retries"]) == (1, 0)

    def test_a_control_that_could_not_run_spends_no_retry_at_all_unlike_a_red_one(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Cli.explain(
            request=TransitionRequestMother.asking(Step.RUN_CONTROLS, Outcome.INDETERMINATE, control_retries=2),
            budgets=Budgets(),
        )

        emitted = json.loads(capsys.readouterr().out)
        assert emitted["state"] == RunState.OPEN
        assert emitted["run"]["control_retries"] == 2

    def test_a_hygiene_rejection_spends_a_retry_of_its_own_and_not_one_of_the_controls(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.RUN_CONTROLS, Outcome.HYGIENE_REJECTED)

        Cli.explain(request=asked, budgets=Budgets())

        spent = json.loads(capsys.readouterr().out)["run"]
        assert (spent["hygiene_retries"], spent["control_retries"]) == (1, 0)

    def test_a_veto_spends_a_retry_of_the_judge_and_not_one_of_the_controls(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Cli.explain(request=TransitionRequestMother.asking(Step.VERIFY, Outcome.FAILED), budgets=Budgets())

        spent = json.loads(capsys.readouterr().out)["run"]
        assert (spent["verify_retries"], spent["control_retries"]) == (1, 0)

    def test_a_veto_spends_a_retry_of_its_own_and_not_one_of_the_corrections(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Cli.explain(request=TransitionRequestMother.asking(Step.VERIFY, Outcome.FAILED), budgets=Budgets())

        spent = json.loads(capsys.readouterr().out)["run"]
        assert (spent["verify_retries"], spent["correction_retries"]) == (1, 0)

    def test_a_discarded_verdict_is_counted_apart_because_the_code_was_never_touched(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Cli.explain(
            request=TransitionRequestMother.asking(Step.VERIFY, Outcome.DISCARDED, verify_retries=2),
            budgets=Budgets(),
        )

        emitted = json.loads(capsys.readouterr().out)
        assert emitted["state"] == RunState.OPEN
        assert (emitted["run"]["verify_discards"], emitted["run"]["verify_retries"]) == (1, 2)

    def test_a_round_of_corrections_spends_a_retry_of_its_own_and_not_one_of_the_veto(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.VERIFY, Outcome.CORRECTIONS_ORDERED, correction_retries=1)

        Cli.explain(request=asked, budgets=Budgets())

        spent = json.loads(capsys.readouterr().out)["run"]
        assert (spent["correction_retries"], spent["verify_retries"]) == (2, 0)

    def test_the_last_corrections_become_debt_instead_of_blocking_a_slice_the_judge_did_not_veto(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.VERIFY, Outcome.CORRECTIONS_ORDERED, correction_retries=2)

        Cli.explain(request=asked, budgets=Budgets())

        emitted = json.loads(capsys.readouterr().out)
        assert (emitted["run"]["step"], emitted["state"]) == (Step.OPEN_PULL_REQUEST, RunState.OPEN)

    def test_the_correction_budget_is_configured_apart_from_the_veto_and_does_not_borrow_its_value(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.VERIFY, Outcome.CORRECTIONS_ORDERED, correction_retries=1)

        Cli.explain(request=asked, budgets=Budgets(correction_retries=1, verify_retries=5))

        emitted = json.loads(capsys.readouterr().out)
        assert (emitted["run"]["step"], emitted["state"]) == (Step.OPEN_PULL_REQUEST, RunState.OPEN)

    def test_an_answer_from_the_ci_clears_the_ticks_that_had_none_because_the_window_wants_them_consecutive(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.AWAIT_CI, Outcome.PENDING, indeterminate_ticks=2)

        Cli.explain(request=asked, budgets=Budgets())

        assert json.loads(capsys.readouterr().out)["run"]["indeterminate_ticks"] == 0


class TestWhenThereIsNoTransitionToExplain:
    @pytest.mark.parametrize(("step", "outcome"), _IMPOSSIBLE)
    def test_a_pair_the_prose_never_describes_is_refused_instead_of_taking_a_generic_branch(
        self, step: Step, outcome: Outcome, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.explain(request=TransitionRequestMother.asking(step, outcome), budgets=Budgets())

        assert code == ExitCode.USAGE_ERROR
        output = capsys.readouterr()
        assert output.out == ""
        assert f"`{step}`" in output.err
        assert f"`{outcome}`" in output.err

    def test_a_run_that_is_not_json_is_refused_because_a_guessed_one_advances_the_wrong_slice(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.explain(request=TransitionRequestMother.not_even_json(), budgets=Budgets())

        assert code == ExitCode.USAGE_ERROR
        assert capsys.readouterr().out == ""

    def test_a_step_nobody_declared_is_refused_instead_of_defaulting_to_the_first_one(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.explain(request=TransitionRequestMother.with_a_step_nobody_declared(), budgets=Budgets())

        assert code == ExitCode.USAGE_ERROR
        assert "deploy" in capsys.readouterr().err

    def test_a_counter_that_arrives_as_text_is_refused_because_it_decides_when_a_budget_runs_out(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.explain(request=TransitionRequestMother.with_a_counter_that_arrives_as_text(), budgets=Budgets())

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


class TestTheCommandThatConductsASlice:
    @staticmethod
    def _complete() -> list[str]:
        return [
            "run",
            str(GhConversationMother.ISSUE),
            "--repo",
            GhConversationMother.REPO,
            "--base",
            GhConversationMother.BASE,
        ]

    def test_it_parses_with_the_issue_as_a_positional_and_the_repo_of_the_issue_and_the_base_as_flags(self) -> None:
        arguments = Cli.parser().parse_args(self._complete())

        assert (arguments.issue, arguments.repo, arguments.base) == (
            GhConversationMother.ISSUE,
            GhConversationMother.REPO,
            GhConversationMother.BASE,
        )

    def test_the_worktree_defaults_to_where_the_command_was_invoked_because_that_is_the_usual_case(self) -> None:
        arguments = Cli.parser().parse_args(self._complete())

        assert arguments.worktree == "."

    def test_the_directory_of_the_control_logs_defaults_to_one_under_the_temporary_of_the_machine(self) -> None:
        arguments = Cli.parser().parse_args(self._complete())

        assert arguments.logs.parent == Path(tempfile.gettempdir())

    def test_the_repo_of_the_issue_has_no_default_because_a_guessed_one_reads_another_issue(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.main(["run", str(GhConversationMother.ISSUE), "--base", GhConversationMother.BASE])

        assert code == ExitCode.USAGE_ERROR
        output = capsys.readouterr()
        assert output.out == ""
        assert "the following arguments are required: --repo" in output.err

    def test_the_base_has_no_default_because_a_guessed_one_opens_the_pull_request_against_the_wrong_branch(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.main(["run", str(GhConversationMother.ISSUE), "--repo", GhConversationMother.REPO])

        assert code == ExitCode.USAGE_ERROR
        assert "the following arguments are required: --base" in capsys.readouterr().err

    def test_the_issue_is_read_as_a_number_so_a_word_is_refused_instead_of_searched_for(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.main(["run", "the-loop", "--repo", GhConversationMother.REPO, "--base", GhConversationMother.BASE])

        assert code == ExitCode.USAGE_ERROR
        assert "the-loop" in capsys.readouterr().err

    def test_asking_for_the_help_of_the_subcommand_is_not_a_usage_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.main(["run", "--help"])

        assert code == ExitCode.OK
        assert "--worktree" in capsys.readouterr().out

    def test_the_slice_defaults_to_none_because_without_it_the_next_runnable_one_is_chosen(self) -> None:
        arguments = Cli.parser().parse_args(self._complete())

        assert arguments.slice_id is None

    def test_the_slice_can_be_named_explicitly_to_conduct_that_one_instead_of_the_next_in_line(self) -> None:
        arguments = Cli.parser().parse_args([*self._complete(), "--slice", _SLICE])

        assert arguments.slice_id == _SLICE


class TestConductingASliceAnEarlierInvocationLeftHalfDone:
    @staticmethod
    def _invocation() -> RunInvocation:
        return RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.awaiting_merge()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "view"), stdout=GhConversationMother.a_merged_pull_request()),
            ),
        )

    def test_it_neither_implements_nor_stages_nor_runs_a_control_because_the_state_says_that_is_done(
        self, tmp_path: Path
    ) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs")

        assert not invocation.process.invoked(ImplementerInvocation.EXECUTABLE)
        assert not invocation.process.invoked("git", "add")
        assert not invocation.process.invoked("sh", "-c", GhConversationMother.CONTROL)

    def test_it_asks_the_forum_for_the_merge_because_that_is_the_step_the_state_left_it_on(
        self, tmp_path: Path
    ) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs")

        assert invocation.process.invoked("gh", "pr", "view", str(GhConversationMother.PULL_REQUEST))

    def test_what_it_emits_is_the_halt_the_state_and_the_step_the_run_stopped_on(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = self._invocation().conduct(logs=tmp_path / "logs")

        assert code == ExitCode.OK
        assert json.loads(capsys.readouterr().out) == {
            "halt": "run-closed",
            "state": "merged",
            "step": "await-merge",
            "pull_request": GhConversationMother.PULL_REQUEST,
        }

    def test_the_directory_of_the_control_logs_is_made_because_a_control_writes_its_log_straight_into_it(
        self, tmp_path: Path
    ) -> None:
        logs = tmp_path / "logs"

        self._invocation().conduct(logs=logs)

        assert logs.is_dir()

    def test_the_transition_that_closes_the_run_is_reported_on_standard_error_leaving_the_result_untouched(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._invocation().conduct(logs=tmp_path / "logs")

        output = capsys.readouterr()
        reported = json.loads(output.err)
        assert (reported["step"], reported["status"]) == ("await-merge", "closed")
        assert json.loads(output.out)["halt"] == "run-closed"


class TestConductingTheSliceNamedByTheCaller:
    @staticmethod
    def _invocation() -> RunInvocation:
        return RunInvocation(
            children=GhConversationMother.two_slices_resumed_at(RunMother.awaiting_merge()),
            parent=GhConversationMother.parent_of_two_slices(),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "view"), stdout=GhConversationMother.a_merged_pull_request()),
            ),
        )

    def test_the_slice_named_by_the_caller_is_conducted_instead_of_the_first_one_in_line(self, tmp_path: Path) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs", slice_id=GhConversationMother.OTHER_SLICE)

        assert invocation.process.invoked("gh", "pr", "list", "--head", GhConversationMother.OTHER_BRANCH)
        assert not invocation.process.invoked("gh", "pr", "list", "--head", GhConversationMother.BRANCH)

    def test_without_the_slice_argument_the_first_one_in_line_is_still_chosen(self, tmp_path: Path) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs")

        assert invocation.process.invoked("gh", "pr", "list", "--head", GhConversationMother.BRANCH)
        assert not invocation.process.invoked("gh", "pr", "list", "--head", GhConversationMother.OTHER_BRANCH)


class TestAskingForASliceThatCannotBeRun:
    def test_a_slice_that_does_not_exist_among_the_issue_fails_closed_without_writing_anything(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.two_slices_resumed_at(RunMother.awaiting_merge()),
            parent=GhConversationMother.parent_of_two_slices(),
        )

        code = invocation.conduct(logs=tmp_path / "logs", slice_id="slice-99")

        assert code == ExitCode.NO_SLICE_LEFT
        assert "slice-99" in capsys.readouterr().err
        assert not invocation.process.invoked("gh", "issue", "edit")
        assert not invocation.process.invoked("gh", "issue", "comment")
        assert not invocation.process.invoked("gh", "pr", "list")

    def test_a_slice_that_is_not_runnable_fails_closed_the_same_way_as_one_that_does_not_exist(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.two_slices_resumed_at(
                RunMother.awaiting_merge(), second_label=IssueLabel.BLOCKED_VERIFY
            ),
            parent=GhConversationMother.parent_of_two_slices(),
            answers=(Answer(to=("gh", "issue", "view", "--json", "comments"), stdout=json.dumps({"comments": []})),),
        )

        code = invocation.conduct(logs=tmp_path / "logs", slice_id=GhConversationMother.OTHER_SLICE)

        assert code == ExitCode.NO_SLICE_LEFT
        assert GhConversationMother.OTHER_SLICE in capsys.readouterr().err
        assert not invocation.process.invoked("gh", "issue", "edit")
        assert not invocation.process.invoked("gh", "pr", "list")


class TestWhenTheRunClosesWithoutBeingMerged:
    def test_a_ci_in_red_with_no_retry_left_exits_with_its_own_code_because_the_issue_has_to_be_looked_at(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.with_the_only_ci_retry_already_spent()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "checks"), stdout=GhConversationMother.checks_in_red()),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.RUN_UNMERGED
        assert json.loads(capsys.readouterr().out) == {
            "halt": "run-closed",
            "state": "blocked-ci-red",
            "step": "await-ci",
            "pull_request": GhConversationMother.PULL_REQUEST,
        }


class TestTheRoundTripAfterARedCiThatStillHasARetryLeft(BlindToTheToolboxOfThisMachine):
    @classmethod
    def _invocation(cls) -> RunInvocation:
        return RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.about_to_ask_the_ci()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "list", "--state", "open"), stdout=GhConversationMother.the_open_pull_request()),
                Answer(to=("gh", "pr", "checks"), stdout=GhConversationMother.checks_in_red()),
                Answer(
                    to=("gh", "issue", "view", "--json", "comments"),
                    stdout=json.dumps({"comments": []}),
                ),
                Answer(
                    to=(ImplementerInvocation.EXECUTABLE, "bypassPermissions"),
                    stdout=json.dumps(HarnessEnvelopeMother.recorded(_IMPLEMENTER_PAYLOAD)),
                ),
                Answer(to=("git", "add")),
                Answer(to=("git", "diff", "--cached", "--name-only"), stdout=cls._what_the_implementer_left_staged()),
                Answer(to=("sh", "-c", GhConversationMother.CONTROL)),
                Answer(to=("git", "diff", "--cached"), stdout="diff --git a/hello.py b/hello.py\n"),
                Answer(
                    to=(JudgeInvocation.EXECUTABLE, "--add-dir"),
                    stdout=json.dumps(HarnessEnvelopeMother.carrying(JudgeVerdictMother.passing())),
                ),
                Answer(to=("git", "symbolic-ref"), stdout=f"{GhConversationMother.BRANCH}\n"),
                Answer(to=("git", "commit")),
                Answer(to=("git", "push")),
            ),
        )

    @staticmethod
    def _what_the_implementer_left_staged() -> str:
        return "hello.py\ntest_hello.py\n"

    def test_the_slice_is_implemented_again_and_walks_the_whole_loop_back_to_the_ci(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = self._invocation()

        code = invocation.conduct(logs=tmp_path / "logs")

        assert invocation.process.invoked(ImplementerInvocation.EXECUTABLE, "bypassPermissions")
        assert code == ExitCode.RUN_UNMERGED
        assert json.loads(capsys.readouterr().out) == {
            "halt": "run-closed",
            "state": "blocked-ci-red",
            "step": "await-ci",
            "pull_request": GhConversationMother.PULL_REQUEST,
        }

    def test_the_code_written_to_fix_the_red_ci_is_committed_and_pushed_so_it_reaches_the_remote(
        self, tmp_path: Path
    ) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs")

        assert invocation.process.invoked("git", "commit")
        assert invocation.process.invoked("git", "push", GhConversationMother.BRANCH)

    def test_the_branch_that_already_carries_its_pull_request_is_not_given_a_second_one(self, tmp_path: Path) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs")

        assert invocation.process.invoked("gh", "pr", "list", "--state", "open")
        assert not invocation.process.invoked("gh", "pr", "create")


class TestWhenTheRunStaysOpen:
    @staticmethod
    def _never_run() -> RunInvocation:
        return RunInvocation(
            children=GhConversationMother.the_slice_never_run(),
            answers=(
                Answer(to=("git", "rev-parse"), code=1),
                Answer(to=("git", "switch")),
                Answer(to=("gh", "pr", "list"), stdout=GhConversationMother.no_open_pull_request()),
                Answer(
                    to=(UnderstandingInvocation.MODEL, "stream-json"),
                    stdout=json.dumps(
                        HarnessEnvelopeMother.carrying(
                            {"understanding": "entiendo la slice y este es mi plan"}, recorded=_IMPLEMENTER_PAYLOAD
                        )
                    ),
                ),
                Answer(to=("gh", "issue", "view", "--json", "comments"), stdout=json.dumps({"comments": []})),
            ),
        )

    def test_the_branch_of_the_slice_is_cut_in_the_worktree_from_the_base_the_invocation_named(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda seconds: None)
        invocation = self._never_run()

        invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(total_wait_seconds=0))

        assert invocation.process.ran(
            "git",
            "-C",
            GhConversationMother.WORKTREE,
            "switch",
            "-c",
            GhConversationMother.BRANCH,
            GhConversationMother.BASE,
        )

    def test_a_slice_that_was_never_run_ticks_through_the_alignment_pause_until_the_wait_runs_out(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        slept: list[int] = []
        monkeypatch.setattr("time.sleep", slept.append)
        invocation = self._never_run()

        code = invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(total_wait_seconds=0))

        assert code == ExitCode.WAIT_EXHAUSTED
        assert sum(slept) == Budgets(total_wait_seconds=0).seconds_between_ticks
        assert json.loads(capsys.readouterr().out) == {
            "halt": "wait-exhausted",
            "state": "open",
            "step": "understand",
        }

    def test_a_precheck_that_is_not_clear_exits_with_its_own_code_and_names_which_one_stopped_it(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_never_run(),
            answers=(
                Answer(to=("git", "rev-parse"), code=1),
                Answer(to=("gh", "pr", "list"), stdout=GhConversationMother.the_open_pull_request()),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.PRECHECKS_BLOCKED
        assert json.loads(capsys.readouterr().out)["precheck"] == "pull-request-already-open"

    def test_a_merge_that_never_arrives_spends_the_whole_wait_and_says_the_pull_request_is_still_draft(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        slept: list[int] = []
        monkeypatch.setattr("time.sleep", slept.append)
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.awaiting_merge()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "view"), stdout=GhConversationMother.a_pull_request_still_open()),
                Answer(to=("gh", "issue", "comment")),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs")
        captured = capsys.readouterr()

        assert code == ExitCode.WAIT_EXHAUSTED
        assert sum(slept) == Budgets().total_wait_seconds
        assert json.loads(captured.out)["halt"] == "wait-exhausted"
        assert invocation.process.invoked("gh", "issue", "comment")
        assert "draft" in captured.err
        assert str(GhConversationMother.PULL_REQUEST) in captured.err

    def test_a_pull_request_closed_without_merging_ends_the_invocation_with_its_own_code_and_no_waiting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        slept: list[int] = []
        monkeypatch.setattr("time.sleep", slept.append)
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.awaiting_merge()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "view"), stdout=GhConversationMother.a_pull_request_closed_without_merging()),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.PULL_REQUEST_CLOSED
        assert slept == []
        assert json.loads(capsys.readouterr().out) == {
            "halt": "pull-request-closed",
            "state": "open",
            "step": "await-merge",
            "pull_request": GhConversationMother.PULL_REQUEST,
        }


class TestWhenTheInvocationCannotBeConducted(ReadingWhatWasReported):
    def test_an_issue_whose_slices_are_all_closed_exits_saying_there_is_nothing_left_to_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(children=GhConversationMother.the_slice_already_closed())

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.NO_SLICE_LEFT
        assert str(GhConversationMother.ISSUE) in self._reported(capsys)

    def test_a_subissue_titled_as_no_slice_is_a_usage_error_and_not_a_run_that_went_wrong(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(children=GhConversationMother.a_title_that_names_no_slice())

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.USAGE_ERROR
        assert "slice-NN" in self._reported(capsys)

    def test_a_gh_that_fails_mid_run_exits_with_the_code_of_an_interrupted_run_carrying_what_it_said(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.awaiting_merge()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(to=("gh", "pr", "list", "--state", "all"), code=1, stderr="gh: authentication required"),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.RUN_INTERRUPTED
        assert "authentication required" in self._reported(capsys)


class TestWhenACallOutlivesItsCap(ReadingWhatWasReported):
    def test_conducting_a_slice_exits_with_the_code_of_the_cap_and_not_with_the_one_that_says_to_reinvoke(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli(process=TimingOutProcess(), budgets=Budgets()).run(RunInvocation.params(logs=tmp_path / "logs"))

        assert code == ExitCode.PROCESS_TIMED_OUT
        assert "gh: killed after 1s" in self._reported(capsys)

    def test_verifying_a_slice_exits_with_the_code_of_the_cap_and_not_with_the_one_of_a_missing_verdict(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli(process=TimingOutProcess(), budgets=Budgets()).verify(
            repo=str(tmp_path), base=Git.BASE_BRANCH, slice_id=_SLICE
        )

        assert code == ExitCode.PROCESS_TIMED_OUT
        assert "git: killed after 1s" in self._reported(capsys)


class TestTheBudgetsTheEntrypointInjects:
    def test_a_conducted_run_waits_the_budget_the_entrypoint_was_given_and_not_one_of_its_own(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        slept: list[int] = []
        monkeypatch.setattr("time.sleep", slept.append)
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.awaiting_merge()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "view"), stdout=GhConversationMother.a_pull_request_still_open()),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(total_wait_seconds=60))

        assert code == ExitCode.WAIT_EXHAUSTED
        assert sum(slept) == 60

    def test_an_explained_transition_ticks_at_the_cadence_the_entrypoint_was_given_and_not_at_one_of_its_own(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.AWAIT_CI, Outcome.PENDING)

        Cli.explain(request=asked, budgets=Budgets(seconds_between_ticks=7))

        assert json.loads(capsys.readouterr().out)["wait_seconds"] == 7
