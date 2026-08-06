from __future__ import annotations

from slice_runner.infrastructure.claude_deploy_watch import ClaudeDeployWatch
from slice_runner.infrastructure.deploy_watch_invocation import DeployWatchInvocation
from slice_runner.tests.doubles import RecordedProcess

_WORKTREE = "/repos/agentic-skills"
_REPO = "alcaptar/agentic-skills"
_SIGNAL = "tasa de error 5xx de shop-web en produccion"


class TestHowDeployWatchIsInvoked:
    @staticmethod
    def _watched() -> RecordedProcess:
        process = RecordedProcess({})

        ClaudeDeployWatch(process=process).watch(worktree=_WORKTREE, repo=_REPO, signal=_SIGNAL)

        return process

    def test_the_argv_is_the_one_the_invocation_composes(self) -> None:
        process = self._watched()

        assert process.argv == DeployWatchInvocation(worktree=_WORKTREE, repo=_REPO, signal=_SIGNAL).argv

    def test_the_prompt_travels_on_standard_input_and_not_in_the_argv(self) -> None:
        process = self._watched()

        assert process.stdin == DeployWatchInvocation(worktree=_WORKTREE, repo=_REPO, signal=_SIGNAL).text
        assert process.stdin not in process.argv

    def test_the_process_runs_from_the_local_worktree_and_not_from_wherever_the_program_was_launched(self) -> None:
        process = self._watched()

        assert process.cwd == _WORKTREE

    def test_it_is_invoked_exactly_once_per_merge(self) -> None:
        process = self._watched()

        assert process.calls == 1
