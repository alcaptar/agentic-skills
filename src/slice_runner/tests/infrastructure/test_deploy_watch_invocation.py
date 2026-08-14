from __future__ import annotations

import pytest

from slice_runner.infrastructure.deploy_watch_invocation import DeployWatchInvocation
from slice_runner.tests.argv import Argv

_WORKTREE = "/repos/agentic-skills"
_REPO = "alcaptar/agentic-skills"
_SIGNAL = "tasa de error 5xx de shop-web en produccion"


class TestWhatDeployWatchIsGranted:
    @pytest.fixture
    def argv(self) -> Argv:
        return Argv(DeployWatchInvocation(worktree=_WORKTREE, repo=_REPO, signal=_SIGNAL).argv)

    def test_it_runs_with_bypassed_permissions_because_no_person_is_there_to_answer_a_prompt(self, argv: Argv) -> None:
        assert argv.value_of("--permission-mode") == "bypassPermissions"

    def test_the_tools_travel_in_a_single_comma_separated_argument(self, argv: Argv) -> None:
        assert argv.value_of("--tools") == "Read,Grep,Glob,Skill,Bash,Agent"

    def test_bash_is_granted_because_deploy_core_runs_as_a_script(self, argv: Argv) -> None:
        assert "Bash" in argv.value_of("--tools").split(",")

    def test_agent_is_granted_because_the_collector_and_the_sre_agent_are_subagents(self, argv: Argv) -> None:
        assert "Agent" in argv.value_of("--tools").split(",")

    def test_the_mcp_servers_are_bounded(self, argv: Argv) -> None:
        assert argv.contains("--strict-mcp-config")

    def test_only_user_settings_load_so_the_destination_repo_does_not_pay_its_own_claude_md(self, argv: Argv) -> None:
        assert argv.value_of("--setting-sources") == "user"

    def test_no_value_follows_another_value_because_each_hangs_from_its_own_flag(self, argv: Argv) -> None:
        assert argv.executable == "claude"
        assert argv.values_that_follow_another_value() == []


class TestWhatTravelsOnStandardInput:
    def test_the_slash_command_resolves_and_carries_the_signal_and_the_destination_repo(self) -> None:
        text = DeployWatchInvocation(worktree=_WORKTREE, repo=_REPO, signal=_SIGNAL).text

        assert text.startswith("/deploy-watch")
        assert _SIGNAL in text
        assert _REPO in text

    def test_the_prompt_does_not_also_travel_in_the_argv(self) -> None:
        invocation = DeployWatchInvocation(worktree=_WORKTREE, repo=_REPO, signal=_SIGNAL)

        assert invocation.text not in invocation.argv

    def test_the_cwd_is_the_local_worktree_so_the_skill_can_infer_the_workload_from_its_files(self) -> None:
        assert DeployWatchInvocation(worktree=_WORKTREE, repo=_REPO, signal=_SIGNAL).cwd == _WORKTREE
