from __future__ import annotations

import json

import pytest

from slice_runner.domain.exceptions import UnreadableForumError
from slice_runner.domain.pull_request_state import PullRequestState
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


class TestGhForumLookingForThePullRequestOfAResumedRun:
    def test_it_asks_gh_for_the_pull_requests_of_this_branch_in_every_state(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="[]", stderr=""))

        GhForum(process=process).any_pull_request(repo=_REPO, branch=_BRANCH)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:3] == ["gh", "pr", "list"]
        assert argv.value_of("--repo") == _REPO
        assert argv.value_of("--head") == _BRANCH
        assert argv.value_of("--state") == "all"
        assert argv.value_of("--json") == "number"

    def test_a_pull_request_already_merged_is_found_because_a_resumed_run_still_has_to_name_it(self) -> None:
        recorded = GhResponseMother.pull_request_of_branch()
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(recorded), stderr=""))

        assert GhForum(process=process).any_pull_request(repo=_REPO, branch=_BRANCH) == 47

    def test_a_branch_that_never_had_a_pull_request_reads_as_none_not_as_zero(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="[]", stderr=""))

        assert GhForum(process=process).any_pull_request(repo=_REPO, branch=_BRANCH) is None

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="GraphQL: Could not resolve to a Repository"))

        with pytest.raises(GhCommandFailedError, match="Could not resolve"):
            GhForum(process=process).any_pull_request(repo=_REPO, branch=_BRANCH)


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


class TestGhForumAskingWhatStateThePullRequestIsIn:
    @staticmethod
    def _answering(state: str) -> ScriptedProcess:
        return ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps({"state": state}), stderr=""))

    def test_it_asks_gh_for_the_state_of_exactly_this_pull_request(self) -> None:
        process = self._answering("MERGED")

        GhForum(process=process).pull_request_state(repo=_REPO, number=60)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:4] == ["gh", "pr", "view", "60"]
        assert argv.value_of("--repo") == _REPO
        assert argv.value_of("--json") == "state"

    def test_a_merged_pull_request_reads_as_merged(self) -> None:
        state = GhForum(process=self._answering("MERGED")).pull_request_state(repo=_REPO, number=60)

        assert state is PullRequestState.MERGED

    def test_a_pull_request_closed_without_merging_is_told_apart_from_one_still_open(self) -> None:
        state = GhForum(process=self._answering("CLOSED")).pull_request_state(repo=_REPO, number=60)

        assert state is PullRequestState.CLOSED

    def test_a_pull_request_still_open_reads_as_open(self) -> None:
        state = GhForum(process=self._answering("OPEN")).pull_request_state(repo=_REPO, number=60)

        assert state is PullRequestState.OPEN

    def test_a_state_that_is_not_one_of_the_three_gh_returns_is_rejected_instead_of_read_as_unmerged(self) -> None:
        with pytest.raises(UnreadableForumError):
            GhForum(process=self._answering("DRAFT")).pull_request_state(repo=_REPO, number=60)

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="no pull requests found for branch"))

        with pytest.raises(GhCommandFailedError, match="no pull requests found"):
            GhForum(process=process).pull_request_state(repo=_REPO, number=60)

    def test_a_response_with_a_key_we_did_not_ask_for_is_rejected_instead_of_read_around(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(code=0, stdout=json.dumps({"state": "MERGED", "mergedAt": "2026-08-05"}), stderr="")
        )

        with pytest.raises(UnreadableForumError):
            GhForum(process=process).pull_request_state(repo=_REPO, number=60)

    def test_a_response_that_is_not_an_object_is_rejected_instead_of_crashing_on_an_attribute(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps([{"state": "MERGED"}]), stderr=""))

        with pytest.raises(UnreadableForumError):
            GhForum(process=process).pull_request_state(repo=_REPO, number=60)


class TestGhForumAskingWhoIsAuthenticated:
    def test_it_asks_gh_for_the_login_of_the_authenticated_user(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="acapdev\n", stderr=""))

        GhForum(process=process).authenticated_as()

        assert process.calls[0].argv == ["gh", "api", "user", "--jq", ".login"]

    def test_the_login_printed_is_returned_stripped_of_its_trailing_newline(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="acapdev\n", stderr=""))

        assert GhForum(process=process).authenticated_as() == "acapdev"

    def test_no_authentication_reads_as_none_instead_of_raising(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="gh: To authenticate, run `gh auth login`"))

        assert GhForum(process=process).authenticated_as() is None


class TestGhForumCheckingWhetherARepoCanBeRead:
    def test_it_asks_gh_to_view_exactly_this_repo(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps({"name": "agentic-skills"}), stderr=""))

        GhForum(process=process).can_read(repo=_REPO)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:3] == ["gh", "repo", "view"]
        assert _REPO in process.calls[0].argv
        assert argv.value_of("--json") == "name"

    def test_a_repo_gh_can_view_reads_as_true(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps({"name": "agentic-skills"}), stderr=""))

        assert GhForum(process=process).can_read(repo=_REPO) is True

    def test_a_repo_gh_cannot_view_reads_as_false_instead_of_raising(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="GraphQL: Could not resolve to a Repository"))

        assert GhForum(process=process).can_read(repo=_REPO) is False
