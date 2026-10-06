from __future__ import annotations

from pathlib import Path

import pytest

from slice_runner.domain.exceptions import UnreachableUpstreamError
from slice_runner.infrastructure.git_upstream import GitUpstream
from slice_runner.infrastructure.process import ProcessNotRunnableError, ProcessOutput, ProcessTimedOutError
from slice_runner.tests.doubles import RaisingOnCommand, ScriptedProcess
from slice_runner.tests.git_repo import Git
from slice_runner.tests.real_process import Real


class TestTheCommitsTheCheckoutLacksThroughTheProcessPort:
    def test_it_fetches_and_then_counts_against_the_configured_upstream_of_the_checkout(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(code=0, stdout="", stderr=""), ProcessOutput(code=0, stdout="4\n", stderr="")
        )

        behind = GitUpstream(process=process).commits_behind(checkout=Path("/repos/agentic-skills"))

        assert behind == 4
        assert [call.argv for call in process.calls] == [
            ["git", "-C", "/repos/agentic-skills", "fetch", "--quiet"],
            ["git", "-C", "/repos/agentic-skills", "rev-list", "--count", "HEAD..@{upstream}"],
        ]

    def test_a_failing_fetch_means_the_remote_could_not_be_asked(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=128, stdout="", stderr="fatal: unable to access"))

        with pytest.raises(UnreachableUpstreamError, match="unable to access"):
            GitUpstream(process=process).commits_behind(checkout=Path("/repos/agentic-skills"))

    def test_a_failing_count_means_the_remote_could_not_be_asked(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(code=0, stdout="", stderr=""),
            ProcessOutput(code=128, stdout="", stderr="fatal: no upstream configured for branch"),
        )

        with pytest.raises(UnreachableUpstreamError, match="no upstream configured"):
            GitUpstream(process=process).commits_behind(checkout=Path("/repos/agentic-skills"))

    @pytest.mark.parametrize("error", [ProcessTimedOutError("too slow"), ProcessNotRunnableError("no git")])
    def test_a_process_that_does_not_answer_means_the_remote_could_not_be_asked(self, error: OSError) -> None:
        process = RaisingOnCommand(when=("fetch",), raises=error)

        with pytest.raises(UnreachableUpstreamError):
            GitUpstream(process=process).commits_behind(checkout=Path("/repos/agentic-skills"))


@pytest.mark.integration
class TestTheCommitsTheCheckoutLacksAgainstARealRemote:
    def test_a_clone_behind_its_remote_counts_the_commits_it_lacks(self, tmp_path: Path) -> None:
        remote = Git.init_repo(tmp_path / "remote")
        Git.run(remote, "commit", "--allow-empty", "-m", "one")
        clone = Git.clone(remote=remote, into=tmp_path / "clone")
        Git.run(remote, "commit", "--allow-empty", "-m", "two")
        Git.run(remote, "commit", "--allow-empty", "-m", "three")

        behind = GitUpstream(process=Real.process()).commits_behind(checkout=clone)

        assert behind == 2

    def test_a_clone_up_to_date_with_its_remote_lacks_nothing(self, tmp_path: Path) -> None:
        remote = Git.init_repo(tmp_path / "remote")
        Git.run(remote, "commit", "--allow-empty", "-m", "one")
        clone = Git.clone(remote=remote, into=tmp_path / "clone")

        behind = GitUpstream(process=Real.process()).commits_behind(checkout=clone)

        assert behind == 0

    def test_a_checkout_without_a_remote_could_not_be_asked(self, tmp_path: Path) -> None:
        repo = Git.init_repo(tmp_path / "repo")
        Git.run(repo, "commit", "--allow-empty", "-m", "one")

        with pytest.raises(UnreachableUpstreamError):
            GitUpstream(process=Real.process()).commits_behind(checkout=repo)
