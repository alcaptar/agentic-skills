from __future__ import annotations

import json
from pathlib import Path

import pytest

from slice_runner.infrastructure.cli import build_parser, run_verify
from slice_runner.tests.git_repo import BASE_BRANCH
from slice_runner.tests.infrastructure.support import (
    RecordedProcess,
    UnrunnableProcess,
    payload,
    repo_with_nothing_staged,
    repo_with_the_slice_staged,
    with_verdict,
)

_HIGH_SEVERITY_FINDING = {
    "regla": "boundaries",
    "path": "mod.py",
    "severidad": "alta",
    "evidencia": "requests in the domain",
    "detalle": "I/O goes behind a port",
}


def test_a_pass_exits_with_zero_and_emits_the_verdict_as_json_on_standard_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = repo_with_the_slice_staged(tmp_path)
    process = RecordedProcess(with_verdict({"veredicto": "PASA", "hallazgos": []}))

    code = run_verify(repo=str(repo), base=BASE_BRANCH, process=process)

    assert code == 0
    assert json.loads(capsys.readouterr().out) == {"veredicto": "PASA", "hallazgos": []}


def test_a_fail_exits_with_one_and_emits_every_finding_whoever_retries_the_slice_needs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = repo_with_the_slice_staged(tmp_path)
    process = RecordedProcess(payload("full-recipe"))

    code = run_verify(repo=str(repo), base=BASE_BRANCH, process=process)

    assert code == 1
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["veredicto"] == "FALLA"
    assert [h["severidad"] for h in emitted["hallazgos"]] == ["alta", "alta", "media", "media"]


def test_an_incoherent_verdict_exits_with_two_instead_of_being_treated_as_a_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = repo_with_the_slice_staged(tmp_path)
    process = RecordedProcess(with_verdict({"veredicto": "PASA", "hallazgos": [_HIGH_SEVERITY_FINDING]}))

    code = run_verify(repo=str(repo), base=BASE_BRANCH, process=process)

    assert code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "PASA con 1 hallazgo" in output.err


def test_a_judge_that_cannot_be_launched_exits_with_two_instead_of_with_the_code_of_the_veto(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = repo_with_the_slice_staged(tmp_path)

    code = run_verify(repo=str(repo), base=BASE_BRANCH, process=UnrunnableProcess())

    assert code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "claude" in output.err


def test_with_nothing_staged_it_exits_with_three_without_spending_an_invocation_of_the_judge(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = repo_with_nothing_staged(tmp_path)
    process = RecordedProcess(with_verdict({"veredicto": "PASA", "hallazgos": []}))

    code = run_verify(repo=str(repo), base=BASE_BRANCH, process=process)

    assert code == 3
    assert process.calls == 0
    assert "staged" in capsys.readouterr().err


def test_a_base_that_does_not_resolve_does_not_exit_with_the_code_of_the_empty_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = repo_with_the_slice_staged(tmp_path)
    process = RecordedProcess(with_verdict({"veredicto": "PASA", "hallazgos": []}))

    code = run_verify(repo=str(repo), base="does-not-exist", process=process)

    assert code == 4
    assert process.calls == 0
    assert "does-not-exist" in capsys.readouterr().err


def test_a_repo_that_does_not_resolve_exits_with_four_without_blaming_the_base(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outside_git = tmp_path / "not-a-repo"
    outside_git.mkdir()
    process = RecordedProcess(with_verdict({"veredicto": "PASA", "hallazgos": []}))

    code = run_verify(repo=str(outside_git), base=BASE_BRANCH, process=process)

    assert code == 4
    assert process.calls == 0
    assert "the repo or the base" in capsys.readouterr().err


def test_the_judge_gets_the_slice_diff_already_materialised_on_disk(tmp_path: Path) -> None:
    repo = repo_with_the_slice_staged(tmp_path)
    process = RecordedProcess(payload("full-recipe"))

    run_verify(repo=str(repo), base=BASE_BRANCH, process=process)

    paths = [line.split(": ", 1)[1] for line in process.stdin.splitlines() if line.startswith("- `slice.diff`")]
    assert len(paths) == 1
    diff = Path(paths[0]).read_text(encoding="utf-8")
    assert "+    return 2" in diff


def test_the_documented_command_parses_with_the_repo_and_the_base() -> None:
    args = build_parser().parse_args(["verify", "--repo", "/repos/project", "--base", "master"])

    assert (args.repo, args.base) == ("/repos/project", "master")


def test_the_base_has_no_default_value_because_a_guessed_one_diffs_the_wrong_range(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["verify", "--repo", "/repos/project"])

    assert "the following arguments are required: --base" in capsys.readouterr().err
