from __future__ import annotations

import json

import pytest

from slice_runner.domain.exceptions import UnreadableForumError
from slice_runner.infrastructure.gh_forum import GhForum
from slice_runner.infrastructure.gh_run_repository import GhCommandFailedError
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import ScriptedProcess
from slice_runner.tests.mothers.gh_response_mother import GhResponseMother

_REPO = "alcaptar/agentic-skills"
_BRANCH = "slice/05-prechecks-deterministas"
_BASE = "master"
_TITLE = "feat(entrega-de-la-slice): commitear solo lo juzgado y abrir la pull request"
_BODY = "## Intencion\nsin esto el programa verifica y no entrega\n\nCloses #46\n"


class TestGhForum:
    def test_it_asks_gh_for_exactly_the_open_pull_requests_of_this_branch(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="[]", stderr=""))

        GhForum(process=process).open_pull_request(repo=_REPO, branch=_BRANCH)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:3] == ["gh", "pr", "list"]
        assert argv.value_of("--repo") == _REPO
        assert argv.value_of("--head") == _BRANCH
        assert argv.value_of("--state") == "open"
        assert argv.value_of("--json") == "number"

    def test_no_open_pull_request_reads_as_none_not_as_zero(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="[]", stderr=""))

        assert GhForum(process=process).open_pull_request(repo=_REPO, branch=_BRANCH) is None

    def test_a_recorded_open_pull_request_gives_back_its_number(self) -> None:
        recorded = GhResponseMother.pull_request_of_branch()
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(recorded), stderr=""))

        assert GhForum(process=process).open_pull_request(repo=_REPO, branch=_BRANCH) == 47

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="GraphQL: Could not resolve to a Repository"))

        with pytest.raises(GhCommandFailedError, match="Could not resolve"):
            GhForum(process=process).open_pull_request(repo=_REPO, branch=_BRANCH)

    def test_a_response_that_is_not_json_is_rejected_instead_of_crashing_on_a_decode_error(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="not json at all", stderr=""))

        with pytest.raises(UnreadableForumError):
            GhForum(process=process).open_pull_request(repo=_REPO, branch=_BRANCH)

    def test_a_response_that_is_not_an_array_is_rejected_too(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps({"number": 47}), stderr=""))

        with pytest.raises(UnreadableForumError):
            GhForum(process=process).open_pull_request(repo=_REPO, branch=_BRANCH)


class TestGhForumOpeningTheSlicePullRequest:
    @staticmethod
    def _created(*, url: str = "https://github.com/alcaptar/agentic-skills/pull/48") -> ScriptedProcess:
        return ScriptedProcess(ProcessOutput(code=0, stdout=f"{url}\n", stderr=""))

    def _create(self, process: ScriptedProcess) -> int:
        return GhForum(process=process).create_pull_request(
            repo=_REPO, branch=_BRANCH, base=_BASE, title=_TITLE, body=_BODY
        )

    def test_it_asks_gh_for_a_draft_of_this_branch_against_this_base(self) -> None:
        process = self._created()

        self._create(process)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:3] == ["gh", "pr", "create"]
        assert argv.value_of("--repo") == _REPO
        assert argv.value_of("--base") == _BASE
        assert argv.value_of("--head") == _BRANCH
        assert argv.value_of("--title") == _TITLE
        assert argv.contains("--draft")

    def test_the_body_travels_by_stdin_so_no_shell_has_to_survive_its_markdown(self) -> None:
        process = self._created()

        self._create(process)

        assert Argv(process.calls[0].argv).value_of("--body-file") == "-"
        assert process.calls[0].stdin == _BODY

    def test_the_number_of_the_pull_request_is_read_from_the_url_gh_printed(self) -> None:
        assert self._create(self._created()) == 48

    def test_a_stdout_that_is_not_a_pull_request_url_is_rejected_instead_of_read_as_a_number(self) -> None:
        with pytest.raises(UnreadableForumError, match="not-a-url"):
            self._create(self._created(url="not-a-url"))

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="a pull request already exists"))

        with pytest.raises(GhCommandFailedError, match="already exists"):
            self._create(process)
