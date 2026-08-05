from __future__ import annotations

import json

import pytest

from slice_runner.domain.exceptions import UnreadableForumError
from slice_runner.infrastructure.gh_forum import GhForum
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.infrastructure.run_repository import GhCommandFailedError
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import ScriptedProcess
from slice_runner.tests.mothers.gh_response_mother import GhResponseMother

_REPO = "alcaptar/agentic-skills"
_BRANCH = "slice/05-prechecks-deterministas"


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
