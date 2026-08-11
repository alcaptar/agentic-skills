from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.check_readiness import CheckReadiness, CheckReadinessParams
from slice_runner.domain.check_verdict import CheckVerdict
from slice_runner.domain.forum import Forum
from slice_runner.domain.skill_library import SkillLibrary
from slice_runner.domain.toolbox import Toolbox

if TYPE_CHECKING:
    from slice_runner.domain.readiness import Readiness
    from slice_runner.domain.readiness_check import ReadinessCheck

_SLICE_SPEC = Path("/home/someone/.claude/skills/slice-spec")
_DEPLOY_WATCH = Path("/home/someone/.claude/skills/deploy-watch")


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
    def skills(self) -> Mock:
        skills: Mock = create_autospec(SkillLibrary, spec_set=True, instance=True)
        skills.installed.side_effect = lambda name: {"slice-spec": _SLICE_SPEC, "deploy-watch": _DEPLOY_WATCH}[name]
        return skills

    @pytest.fixture
    def query(self, toolbox: Mock, forum: Mock, skills: Mock) -> CheckReadiness:
        return CheckReadiness(toolbox=toolbox, forum=forum, skills=skills)

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
