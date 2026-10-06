from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.check_readiness import CheckReadiness, CheckReadinessParams, CheckReadinessPorts
from slice_runner.domain.branches import Branches
from slice_runner.domain.check_verdict import CheckVerdict
from slice_runner.domain.exceptions import (
    UnreachableUpstreamError,
    UnreadableProvenanceError,
    UnresolvableBaseError,
)
from slice_runner.domain.forum import Forum
from slice_runner.domain.installed_code import InstalledCode
from slice_runner.domain.installed_code_match import InstalledCodeMatch
from slice_runner.domain.plugin_registry import PluginRegistry
from slice_runner.domain.provenance import Provenance
from slice_runner.domain.skill_library import SkillLibrary
from slice_runner.domain.toolbox import Toolbox
from slice_runner.domain.upstream import Upstream

if TYPE_CHECKING:
    from slice_runner.domain.readiness import Readiness
    from slice_runner.domain.readiness_check import ReadinessCheck

_SLICE_SPEC = Path("/home/someone/.claude/skills/slice-spec")
_DEPLOY_WATCH = Path("/home/someone/.claude/skills/deploy-watch")
_HELPER_PATHS = {relative: Path(f"/home/someone/.claude/{relative}") for relative in CheckReadiness.HELPERS}
_CHECKOUT = Path("/home/someone/repos/agentic-skills")


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
        skills.root.return_value = Path("/home/someone/.claude")
        skills.installed.side_effect = lambda name: {"slice-spec": _SLICE_SPEC, "deploy-watch": _DEPLOY_WATCH}[name]
        skills.file.side_effect = lambda relative: _HELPER_PATHS[relative]
        skills.checkout.return_value = _CHECKOUT
        return skills

    @pytest.fixture
    def plugins(self) -> Mock:
        plugins: Mock = create_autospec(PluginRegistry, spec_set=True, instance=True)
        plugins.enabled.return_value = True
        return plugins

    @pytest.fixture
    def provenance(self) -> Mock:
        provenance: Mock = create_autospec(Provenance, spec_set=True, instance=True)
        provenance.checkout.return_value = _CHECKOUT
        return provenance

    @pytest.fixture
    def installed_code(self) -> Mock:
        installed_code: Mock = create_autospec(InstalledCode, spec_set=True, instance=True)
        installed_code.compared_with.return_value = InstalledCodeMatch.SAME
        return installed_code

    @pytest.fixture
    def upstream(self) -> Mock:
        upstream: Mock = create_autospec(Upstream, spec_set=True, instance=True)
        upstream.commits_behind.return_value = 0
        return upstream

    @pytest.fixture
    def query(
        self,
        *,
        toolbox: Mock,
        forum: Mock,
        branches: Mock,
        skills: Mock,
        plugins: Mock,
        provenance: Mock,
        installed_code: Mock,
        upstream: Mock,
    ) -> CheckReadiness:
        return CheckReadiness(
            ports=CheckReadinessPorts(
                toolbox=toolbox,
                forum=forum,
                branches=branches,
                skills=skills,
                plugins=plugins,
                provenance=provenance,
                installed_code=installed_code,
                upstream=upstream,
            )
        )

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

    def test_a_missing_skill_is_reported_with_the_install_command_that_fixes_it(
        self, query: CheckReadiness, skills: Mock
    ) -> None:
        skills.installed.side_effect = lambda name: None if name == "deploy-watch" else _SLICE_SPEC

        readiness = query.execute(CheckReadinessParams())

        deploy_watch = self._check(readiness, "skill deploy-watch")
        assert deploy_watch.verdict is CheckVerdict.MISSING
        assert deploy_watch.fix is not None
        assert "make install-skills" in deploy_watch.fix

    def test_a_missing_skill_fix_names_the_configuration_directory_the_doctor_just_looked_at(
        self, query: CheckReadiness, skills: Mock
    ) -> None:
        skills.root.return_value = Path("/repos/agentic-skills-checkout/.claude-moved")
        skills.installed.side_effect = lambda name: None if name == "deploy-watch" else _SLICE_SPEC

        readiness = query.execute(CheckReadinessParams())

        deploy_watch = self._check(readiness, "skill deploy-watch")
        assert deploy_watch.fix is not None
        assert "/repos/agentic-skills-checkout/.claude-moved" in deploy_watch.fix
        assert "~/.claude" not in deploy_watch.fix

    def test_no_skill_or_helper_fix_leaves_a_placeholder_to_fill_in_by_hand(
        self, query: CheckReadiness, skills: Mock
    ) -> None:
        skills.installed.side_effect = None
        skills.installed.return_value = None
        skills.file.side_effect = None
        skills.file.return_value = None

        readiness = query.execute(CheckReadinessParams())

        fixes = [
            check.fix
            for check in readiness.checks
            if check.name.startswith("skill ") or check.name.startswith("helper ")
        ]
        assert fixes
        assert all(fix is not None and "<checkout>" not in fix for fix in fixes)

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

    def test_a_missing_helper_is_reported_with_the_install_command_that_fixes_it(
        self, query: CheckReadiness, skills: Mock
    ) -> None:
        skills.file.side_effect = lambda relative: (
            None if relative.endswith("discover_conventions.py") else _HELPER_PATHS[relative]
        )

        readiness = query.execute(CheckReadinessParams())

        helper = self._check(readiness, "helper discover_conventions.py")
        assert helper.verdict is CheckVerdict.MISSING
        assert helper.fix is not None
        assert "make install-skills" in helper.fix
        assert not readiness.ready

    def test_a_missing_helper_fix_names_the_configuration_directory_the_doctor_just_looked_at(
        self, query: CheckReadiness, skills: Mock
    ) -> None:
        skills.root.return_value = Path("/repos/agentic-skills-checkout/.claude-moved")
        skills.file.side_effect = lambda relative: (
            None if relative.endswith("discover_conventions.py") else _HELPER_PATHS[relative]
        )

        readiness = query.execute(CheckReadinessParams())

        helper = self._check(readiness, "helper discover_conventions.py")
        assert helper.fix is not None
        assert "/repos/agentic-skills-checkout/.claude-moved" in helper.fix
        assert "~/.claude" not in helper.fix

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
            "provenance",
            "installed code",
            "checkout upstream",
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

    def test_the_provenance_check_is_ready_naming_the_shared_checkout_when_both_sides_agree(
        self, query: CheckReadiness
    ) -> None:
        readiness = query.execute(CheckReadinessParams())

        provenance = self._check(readiness, "provenance")
        assert provenance.verdict is CheckVerdict.READY
        assert str(_CHECKOUT) in provenance.detail
        assert readiness.ready

    def test_the_provenance_check_is_not_ready_with_both_paths_when_the_program_and_the_skills_disagree(
        self, query: CheckReadiness, skills: Mock
    ) -> None:
        skills.checkout.return_value = Path("/repos/agentic-skills-worktree")

        readiness = query.execute(CheckReadinessParams())

        provenance = self._check(readiness, "provenance")
        assert provenance.verdict is CheckVerdict.MISSING
        assert str(_CHECKOUT) in provenance.detail
        assert "/repos/agentic-skills-worktree" in provenance.detail
        assert not readiness.ready

    def test_the_provenance_check_is_not_ready_when_the_two_skills_it_names_disagree_with_each_other(
        self, query: CheckReadiness, skills: Mock
    ) -> None:
        elsewhere = Path("/repos/agentic-skills-worktree")
        skills.checkout.side_effect = lambda name: _CHECKOUT if name == "slice-spec" else elsewhere

        readiness = query.execute(CheckReadinessParams())

        provenance = self._check(readiness, "provenance")
        assert provenance.verdict is CheckVerdict.MISSING
        assert "deploy-watch" in provenance.detail
        assert str(elsewhere) in provenance.detail

    def test_the_provenance_check_is_not_ready_saying_it_could_not_check_when_the_program_origin_cannot_be_read(
        self, query: CheckReadiness, provenance: Mock
    ) -> None:
        provenance.checkout.side_effect = UnreadableProvenanceError("no direct_url.json found")

        readiness = query.execute(CheckReadinessParams())

        check = self._check(readiness, "provenance")
        assert check.verdict is CheckVerdict.MISSING
        assert "could not" in check.detail

    def test_the_provenance_check_is_not_ready_when_a_named_skill_is_not_installed(
        self, query: CheckReadiness, skills: Mock
    ) -> None:
        skills.checkout.side_effect = lambda name: None if name == "deploy-watch" else _CHECKOUT

        readiness = query.execute(CheckReadinessParams())

        provenance = self._check(readiness, "provenance")
        assert provenance.verdict is CheckVerdict.MISSING
        assert "deploy-watch" in provenance.detail

    def test_the_installed_code_check_is_ready_when_it_is_the_one_of_the_checkout(
        self, query: CheckReadiness, installed_code: Mock
    ) -> None:
        readiness = query.execute(CheckReadinessParams())

        check = self._check(readiness, "installed code")
        assert check.verdict is CheckVerdict.READY
        installed_code.compared_with.assert_called_once_with(checkout=_CHECKOUT)

    def test_the_installed_code_check_is_not_ready_telling_to_reinstall_when_it_differs_from_the_checkout(
        self, query: CheckReadiness, installed_code: Mock
    ) -> None:
        installed_code.compared_with.return_value = InstalledCodeMatch.DIFFERENT

        readiness = query.execute(CheckReadinessParams())

        check = self._check(readiness, "installed code")
        assert check.verdict is CheckVerdict.MISSING
        assert check.fix == f"make -C {_CHECKOUT} install-program"
        assert not readiness.ready

    def test_the_installed_code_check_is_not_ready_saying_the_checkout_is_gone_when_it_no_longer_exists(
        self, query: CheckReadiness, installed_code: Mock
    ) -> None:
        installed_code.compared_with.return_value = InstalledCodeMatch.CHECKOUT_GONE

        readiness = query.execute(CheckReadinessParams())

        check = self._check(readiness, "installed code")
        assert check.verdict is CheckVerdict.MISSING
        assert "no longer exists" in check.detail
        assert str(_CHECKOUT) in check.detail
        assert not readiness.ready

    def test_the_installed_code_check_is_not_ready_when_the_checkout_it_came_from_cannot_be_read(
        self, query: CheckReadiness, provenance: Mock, installed_code: Mock
    ) -> None:
        provenance.checkout.side_effect = UnreadableProvenanceError("no direct_url.json found")

        readiness = query.execute(CheckReadinessParams())

        check = self._check(readiness, "installed code")
        assert check.verdict is CheckVerdict.MISSING
        assert "no direct_url.json found" in check.detail
        installed_code.compared_with.assert_not_called()

    def test_the_installed_code_check_could_not_be_checked_when_the_comparison_fails_and_does_not_break_readiness(
        self, query: CheckReadiness, installed_code: Mock
    ) -> None:
        installed_code.compared_with.side_effect = UnreadableProvenanceError("diff: trouble")

        readiness = query.execute(CheckReadinessParams())

        check = self._check(readiness, "installed code")
        assert check.verdict is CheckVerdict.UNKNOWN
        assert "diff: trouble" in check.detail
        assert readiness.ready

    def test_the_upstream_check_is_ready_when_the_checkout_is_not_behind_its_remote_branch(
        self, query: CheckReadiness, upstream: Mock
    ) -> None:
        readiness = query.execute(CheckReadinessParams())

        check = self._check(readiness, "checkout upstream")
        assert check.verdict is CheckVerdict.READY
        upstream.commits_behind.assert_called_once_with(checkout=_CHECKOUT)

    def test_the_upstream_check_is_not_ready_saying_how_many_commits_the_checkout_lacks(
        self, query: CheckReadiness, upstream: Mock
    ) -> None:
        upstream.commits_behind.return_value = 3

        readiness = query.execute(CheckReadinessParams())

        check = self._check(readiness, "checkout upstream")
        assert check.verdict is CheckVerdict.MISSING
        assert "3 commit(s)" in check.detail
        assert check.fix == f"git -C {_CHECKOUT} pull, then make -C {_CHECKOUT} install-program"
        assert not readiness.ready

    def test_the_upstream_check_could_not_be_checked_when_the_remote_cannot_be_asked_and_does_not_break_readiness(
        self, query: CheckReadiness, upstream: Mock
    ) -> None:
        upstream.commits_behind.side_effect = UnreachableUpstreamError("could not resolve host")

        readiness = query.execute(CheckReadinessParams())

        check = self._check(readiness, "checkout upstream")
        assert check.verdict is CheckVerdict.UNKNOWN
        assert "could not resolve host" in check.detail
        assert readiness.ready

    def test_the_upstream_check_could_not_be_checked_when_the_checkout_cannot_be_read(
        self, query: CheckReadiness, provenance: Mock, upstream: Mock
    ) -> None:
        provenance.checkout.side_effect = UnreadableProvenanceError("no direct_url.json found")

        readiness = query.execute(CheckReadinessParams())

        check = self._check(readiness, "checkout upstream")
        assert check.verdict is CheckVerdict.UNKNOWN
        upstream.commits_behind.assert_not_called()

    def test_the_base_check_is_emitted_the_same_with_the_new_checks_in_place(
        self, query: CheckReadiness, branches: Mock, upstream: Mock
    ) -> None:
        branches.commits_behind_remote.return_value = 2
        upstream.commits_behind.return_value = 5

        readiness = query.execute(CheckReadinessParams(worktree="/repos/agentic-skills", base="master"))

        base = self._check(readiness, "base")
        assert base.verdict is CheckVerdict.WARNING
        assert base.detail == "master is 2 commit(s) behind its remote"
        branches.commits_behind_remote.assert_called_once_with(worktree="/repos/agentic-skills", base="master")
