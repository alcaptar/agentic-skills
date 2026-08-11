from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.check_readiness import CheckReadiness, CheckReadinessParams
from slice_runner.domain.branches import Branches
from slice_runner.domain.check_verdict import CheckVerdict
from slice_runner.domain.exceptions import UnresolvableBaseError
from slice_runner.domain.forum import Forum
from slice_runner.domain.plugin_registry import PluginRegistry
from slice_runner.domain.skill_library import SkillLibrary
from slice_runner.domain.toolbox import Toolbox

if TYPE_CHECKING:
    from slice_runner.domain.readiness import Readiness
    from slice_runner.domain.readiness_check import ReadinessCheck

_SLICE_SPEC = Path("/home/someone/.claude/skills/slice-spec")
_DEPLOY_WATCH = Path("/home/someone/.claude/skills/deploy-watch")
_HELPER_PATHS = {relative: Path(f"/home/someone/.claude/{relative}") for relative in CheckReadiness.HELPERS}


class TestCheckReadiness:
    @pytest.fixture
    def toolbox(self) -> Mock:
        toolbox: Mock = create_autospec(Toolbox, spec_set=True, instance=True)
        toolbox.version_of.return_value = "2.51.0"
        return toolbox

    @pytest.fixture
    def forum(self) -> Mock:
        forum: Mock = create_autospec(Forum, spec_set=True, instance=True)
        forum.authenticated_as.return_value = "acapdev"
        return forum

    @pytest.fixture
    def branches(self) -> Mock:
        branches: Mock = create_autospec(Branches, spec_set=True, instance=True)
        branches.commits_behind_remote.return_value = 0
        return branches

    @pytest.fixture
    def skills(self) -> Mock:
        skills: Mock = create_autospec(SkillLibrary, spec_set=True, instance=True)
        skills.installed.side_effect = lambda name: {"slice-spec": _SLICE_SPEC, "deploy-watch": _DEPLOY_WATCH}[name]
        skills.file.side_effect = lambda relative: _HELPER_PATHS[relative]
        return skills

    @pytest.fixture
    def plugins(self) -> Mock:
        plugins: Mock = create_autospec(PluginRegistry, spec_set=True, instance=True)
        plugins.enabled.return_value = True
        return plugins

    @pytest.fixture
    def query(self, toolbox: Mock, forum: Mock, branches: Mock, skills: Mock, plugins: Mock) -> CheckReadiness:
        return CheckReadiness(toolbox=toolbox, forum=forum, branches=branches, skills=skills, plugins=plugins)

    @staticmethod
    def _check(readiness: Readiness, name: str) -> ReadinessCheck:
        return next(check for check in readiness.checks if check.name == name)

    def test_with_everything_in_place_the_readiness_is_ready(self, query: CheckReadiness) -> None:
        readiness = query.execute(CheckReadinessParams())

        assert readiness.ready
        assert all(check.verdict is CheckVerdict.READY for check in readiness.checks)

    def test_it_checks_exactly_the_two_skills_the_rubric_names(self, query: CheckReadiness, skills: Mock) -> None:
        query.execute(CheckReadinessParams())

        checked = {call.args[0] for call in skills.installed.call_args_list}
        assert checked == {"slice-spec", "deploy-watch"}

    def test_a_missing_git_is_reported_as_missing_with_a_fix_command_and_breaks_readiness(
        self, query: CheckReadiness, toolbox: Mock
    ) -> None:
        toolbox.version_of.side_effect = lambda executable: None if executable == "git" else "2.1.4"

        readiness = query.execute(CheckReadinessParams())

        git = self._check(readiness, "git")
        assert git.verdict is CheckVerdict.MISSING
        assert git.fix
        assert not readiness.ready

    def test_gh_present_but_not_authenticated_is_missing_with_the_login_command_as_its_fix(
        self, query: CheckReadiness, forum: Mock
    ) -> None:
        forum.authenticated_as.return_value = None

        readiness = query.execute(CheckReadinessParams())

        gh = self._check(readiness, "gh")
        assert gh.verdict is CheckVerdict.MISSING
        assert gh.fix == "gh auth login"

    def test_gh_missing_outright_is_not_asked_whether_it_is_authenticated_too(
        self, query: CheckReadiness, toolbox: Mock, forum: Mock
    ) -> None:
        toolbox.version_of.side_effect = lambda executable: None if executable == "gh" else "2.1.4"

        readiness = query.execute(CheckReadinessParams())

        forum.authenticated_as.assert_not_called()
        assert self._check(readiness, "gh").verdict is CheckVerdict.MISSING

    def test_claude_is_asked_for_its_version_and_nothing_else_because_a_real_call_costs_money(
        self, query: CheckReadiness, toolbox: Mock
    ) -> None:
        query.execute(CheckReadinessParams())

        assert any(call.args == ("claude",) for call in toolbox.version_of.call_args_list)

    def test_a_missing_skill_is_reported_with_the_symlink_command_that_installs_it(
        self, query: CheckReadiness, skills: Mock
    ) -> None:
        skills.installed.side_effect = lambda name: None if name == "deploy-watch" else _SLICE_SPEC

        readiness = query.execute(CheckReadinessParams())

        deploy_watch = self._check(readiness, "skill deploy-watch")
        assert deploy_watch.verdict is CheckVerdict.MISSING
        assert deploy_watch.fix is not None
        assert "deploy-watch" in deploy_watch.fix
        assert "ln -s" in deploy_watch.fix

    def test_the_superpowers_plugin_enabled_is_reported_as_ready(self, query: CheckReadiness, plugins: Mock) -> None:
        plugins.enabled.return_value = True

        readiness = query.execute(CheckReadinessParams())

        plugin = self._check(readiness, "plugin superpowers")
        assert plugin.verdict is CheckVerdict.READY
        assert readiness.ready

    def test_the_superpowers_plugin_not_enabled_is_reported_as_missing_and_breaks_readiness(
        self, query: CheckReadiness, plugins: Mock
    ) -> None:
        plugins.enabled.return_value = False

        readiness = query.execute(CheckReadinessParams())

        plugin = self._check(readiness, "plugin superpowers")
        assert plugin.verdict is CheckVerdict.MISSING
        assert plugin.fix
        assert not readiness.ready

    def test_a_helper_present_at_its_absolute_path_is_reported_as_ready(
        self, query: CheckReadiness, skills: Mock
    ) -> None:
        readiness = query.execute(CheckReadinessParams())

        helper = self._check(readiness, "helper discover_conventions.py")
        assert helper.verdict is CheckVerdict.READY
        assert readiness.ready

    def test_a_missing_helper_is_reported_with_the_symlink_command_that_installs_its_directory(
        self, query: CheckReadiness, skills: Mock
    ) -> None:
        skills.file.side_effect = lambda relative: (
            None if relative.endswith("discover_conventions.py") else _HELPER_PATHS[relative]
        )

        readiness = query.execute(CheckReadinessParams())

        helper = self._check(readiness, "helper discover_conventions.py")
        assert helper.verdict is CheckVerdict.MISSING
        assert helper.fix is not None
        assert "slice-runner" in helper.fix
        assert "ln -s" in helper.fix
        assert not readiness.ready

    def test_without_repo_worktree_or_base_only_the_checks_that_need_none_of_them_run(
        self, query: CheckReadiness, forum: Mock, branches: Mock
    ) -> None:
        readiness = query.execute(CheckReadinessParams())

        assert {check.name for check in readiness.checks} == {
            "git",
            "gh",
            "claude",
            "skill slice-spec",
            "skill deploy-watch",
            "plugin superpowers",
            "helper discover_conventions.py",
            "helper discover_controles.py",
        }
        forum.can_read.assert_not_called()
        branches.commits_behind_remote.assert_not_called()

    def test_with_repo_readable_the_repo_check_is_ready(self, query: CheckReadiness, forum: Mock) -> None:
        forum.can_read.return_value = True

        readiness = query.execute(CheckReadinessParams(repo="alcaptar/agentic-skills"))

        repo = self._check(readiness, "repo")
        assert repo.verdict is CheckVerdict.READY

    def test_with_repo_unreadable_the_repo_check_is_missing_with_a_fix_and_breaks_readiness(
        self, query: CheckReadiness, forum: Mock
    ) -> None:
        forum.can_read.return_value = False

        readiness = query.execute(CheckReadinessParams(repo="alcaptar/agentic-skills"))

        repo = self._check(readiness, "repo")
        assert repo.verdict is CheckVerdict.MISSING
        assert repo.fix
        assert not readiness.ready

    def test_with_worktree_and_base_up_to_date_the_base_check_is_ready(
        self, query: CheckReadiness, branches: Mock
    ) -> None:
        branches.commits_behind_remote.return_value = 0

        readiness = query.execute(CheckReadinessParams(worktree="/repos/agentic-skills", base="master"))

        base = self._check(readiness, "base")
        assert base.verdict is CheckVerdict.READY

    def test_with_worktree_and_base_behind_its_remote_the_base_check_warns_with_the_command_that_updates_it(
        self, query: CheckReadiness, branches: Mock
    ) -> None:
        branches.commits_behind_remote.return_value = 2

        readiness = query.execute(CheckReadinessParams(worktree="/repos/agentic-skills", base="master"))

        base = self._check(readiness, "base")
        assert base.verdict is CheckVerdict.WARNING
        assert base.fix
        assert "master" in base.fix

    def test_a_lagging_base_warning_alone_does_not_flip_readiness_to_not_ready(
        self, query: CheckReadiness, branches: Mock
    ) -> None:
        branches.commits_behind_remote.return_value = 2

        readiness = query.execute(CheckReadinessParams(worktree="/repos/agentic-skills", base="master"))

        assert readiness.ready

    def test_a_base_that_does_not_resolve_against_its_remote_is_reported_as_missing_naming_the_base(
        self, query: CheckReadiness, branches: Mock
    ) -> None:
        branches.commits_behind_remote.side_effect = UnresolvableBaseError("slice/05-never-pushed does not resolve")

        readiness = query.execute(CheckReadinessParams(worktree="/repos/agentic-skills", base="slice/05-never-pushed"))

        base = self._check(readiness, "base")
        assert base.verdict is CheckVerdict.MISSING
        assert "slice/05-never-pushed" in base.detail
        assert not readiness.ready

    def test_worktree_without_base_does_not_run_the_base_check(self, query: CheckReadiness, branches: Mock) -> None:
        readiness = query.execute(CheckReadinessParams(worktree="/repos/agentic-skills"))

        assert not any(check.name == "base" for check in readiness.checks)
        branches.commits_behind_remote.assert_not_called()
