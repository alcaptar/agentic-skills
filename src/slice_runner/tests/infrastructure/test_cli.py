from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.tests.doubles import RealExceptTheJudge, UnrunnableJudge
from slice_runner.tests.git_repo import Git
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother, JudgeVerdictMother
from slice_runner.tests.mothers.repo_mother import RepoMother


@pytest.mark.integration
class TestTheExitCodeOfTheVerdict:
    def test_a_pass_exits_with_zero_and_emits_the_verdict_as_json_on_standard_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.carrying(JudgeVerdictMother.passing()))

        code = Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH)

        assert code == ExitCode.PASS
        assert json.loads(capsys.readouterr().out) == {"veredicto": "PASA", "hallazgos": []}

    def test_a_fail_exits_with_one_and_emits_every_finding_whoever_retries_the_slice_needs(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.recorded())

        code = Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH)

        assert code == ExitCode.FAIL
        emitted = json.loads(capsys.readouterr().out)
        assert emitted["veredicto"] == "FALLA"
        assert [finding["severidad"] for finding in emitted["hallazgos"]] == ["alta", "alta", "media", "media"]


@pytest.mark.integration
class TestWhenThereIsNoVerdictToTrust:
    def test_an_incoherent_verdict_exits_with_two_instead_of_being_treated_as_a_pass(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        incoherent = JudgeVerdictMother.passing_with(JudgeVerdictMother.high_severity_finding(path="mod.py"))
        process = RealExceptTheJudge(HarnessEnvelopeMother.carrying(incoherent))

        code = Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH)

        assert code == ExitCode.NO_USABLE_VERDICT
        output = capsys.readouterr()
        assert output.out == ""
        assert "PASA with 1 hallazgo" in output.err

    def test_a_judge_that_cannot_be_launched_exits_with_two_instead_of_with_the_code_of_the_veto(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        code = Cli(process=UnrunnableJudge()).verify(repo=str(repo), base=Git.BASE_BRANCH)

        assert code == ExitCode.NO_USABLE_VERDICT
        output = capsys.readouterr()
        assert output.out == ""
        assert "claude" in output.err


@pytest.mark.integration
class TestWhenThereIsNothingToJudge:
    @pytest.fixture
    def process(self) -> RealExceptTheJudge:
        return RealExceptTheJudge(HarnessEnvelopeMother.carrying(JudgeVerdictMother.passing()))

    def test_with_nothing_staged_it_exits_with_three_without_spending_an_invocation_of_the_judge(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], process: RealExceptTheJudge
    ) -> None:
        repo = RepoMother.with_nothing_staged(tmp_path)

        code = Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH)

        assert code == ExitCode.NO_DIFF
        assert process.calls == 0
        assert "staged" in capsys.readouterr().err

    def test_a_base_that_does_not_resolve_does_not_exit_with_the_code_of_the_empty_index(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], process: RealExceptTheJudge
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        code = Cli(process=process).verify(repo=str(repo), base="does-not-exist")

        assert code == ExitCode.USAGE_ERROR
        assert process.calls == 0
        assert "does-not-exist" in capsys.readouterr().err

    def test_a_repo_that_does_not_resolve_exits_with_four_without_blaming_the_base(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], process: RealExceptTheJudge
    ) -> None:
        code = Cli(process=process).verify(repo=str(RepoMother.outside_git(tmp_path)), base=Git.BASE_BRANCH)

        assert code == ExitCode.USAGE_ERROR
        assert process.calls == 0
        assert "the repo or the base" in capsys.readouterr().err


@pytest.mark.integration
class TestTheDiffTheJudgeReads:
    def test_the_judge_gets_the_diff_already_written_to_disk(self, tmp_path: Path) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        process = RealExceptTheJudge(HarnessEnvelopeMother.recorded())

        Cli(process=process).verify(repo=str(repo), base=Git.BASE_BRANCH)

        assert "+    return 2" in self._diff_the_prompt_points_at(process.stdin)

    @staticmethod
    def _diff_the_prompt_points_at(prompt: str) -> str:
        pointers = [line.split(": ", 1)[1] for line in prompt.splitlines() if line.startswith("- `slice.diff`")]
        assert len(pointers) == 1

        return Path(pointers[0]).read_text(encoding="utf-8")


@pytest.mark.integration
class TestTheEntrypoint:
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

        code = Cli.main(["verify", "--repo", str(repo), "--base", Git.BASE_BRANCH])

        assert code == ExitCode.NO_DIFF
        assert "staged" in capsys.readouterr().err

    def test_main_reports_the_base_it_was_given_and_not_a_guessed_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        code = Cli.main(["verify", "--repo", str(repo), "--base", "a-base-that-is-not-there"])

        assert code == ExitCode.USAGE_ERROR
        assert "a-base-that-is-not-there" in capsys.readouterr().err


class TestTheDocumentedCommand:
    def test_it_parses_with_the_repo_and_the_base(self) -> None:
        arguments = Cli.parser().parse_args(["verify", "--repo", "/repos/project", "--base", "master"])

        assert (arguments.repo, arguments.base) == ("/repos/project", "master")

    def test_the_base_has_no_default_value_because_a_guessed_one_diffs_the_wrong_range(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(["verify", "--repo", "/repos/project"])

        assert "the following arguments are required: --base" in capsys.readouterr().err
