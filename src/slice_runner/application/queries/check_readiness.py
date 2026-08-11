from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.check_verdict import CheckVerdict
from slice_runner.domain.readiness import Readiness
from slice_runner.domain.readiness_check import ReadinessCheck

if TYPE_CHECKING:
    from slice_runner.domain.branches import Branches
    from slice_runner.domain.forum import Forum
    from slice_runner.domain.skill_library import SkillLibrary
    from slice_runner.domain.toolbox import Toolbox


@dataclass(frozen=True, kw_only=True, slots=True)
class CheckReadinessParams:
    repo: str | None = None
    worktree: str | None = None
    base: str | None = None


class CheckReadiness:
    SKILLS: ClassVar[tuple[str, ...]] = ("slice-spec", "deploy-watch")

    def __init__(self, *, toolbox: Toolbox, forum: Forum, branches: Branches, skills: SkillLibrary) -> None:
        self._toolbox = toolbox
        self._forum = forum
        self._branches = branches
        self._skills = skills

    def execute(self, params: CheckReadinessParams) -> Readiness:
        checks = [
            self._of_git(),
            self._of_gh(),
            self._of_claude(),
            *(self._of_skill(name) for name in self.SKILLS),
        ]
        if params.repo is not None:
            checks.append(self._of_repo(params.repo))
        if params.worktree is not None and params.base is not None:
            checks.append(self._of_base(worktree=params.worktree, base=params.base))

        return Readiness(checks=tuple(checks))

    def _of_git(self) -> ReadinessCheck:
        version = self._toolbox.version_of("git")
        if version is None:
            return ReadinessCheck(
                name="git",
                verdict=CheckVerdict.MISSING,
                detail="not found on the PATH",
                fix="install git: https://git-scm.com/downloads",
            )

        return ReadinessCheck(name="git", verdict=CheckVerdict.READY, detail=version)

    def _of_gh(self) -> ReadinessCheck:
        version = self._toolbox.version_of("gh")
        if version is None:
            return ReadinessCheck(
                name="gh",
                verdict=CheckVerdict.MISSING,
                detail="not found on the PATH",
                fix="install the GitHub CLI: https://cli.github.com",
            )

        who = self._forum.authenticated_as()
        if who is None:
            return ReadinessCheck(
                name="gh", verdict=CheckVerdict.MISSING, detail="not authenticated", fix="gh auth login"
            )

        return ReadinessCheck(name="gh", verdict=CheckVerdict.READY, detail=f"authenticated as {who}")

    def _of_claude(self) -> ReadinessCheck:
        version = self._toolbox.version_of("claude")
        if version is None:
            return ReadinessCheck(
                name="claude",
                verdict=CheckVerdict.MISSING,
                detail="not found on the PATH",
                fix="install Claude Code: npm install -g @anthropic-ai/claude-code",
            )

        return ReadinessCheck(name="claude", verdict=CheckVerdict.READY, detail=version)

    def _of_skill(self, name: str) -> ReadinessCheck:
        path = self._skills.installed(name)
        if path is None:
            return ReadinessCheck(
                name=f"skill {name}",
                verdict=CheckVerdict.MISSING,
                detail="not installed",
                fix=f"ln -s <checkout>/skills/{name} ~/.claude/skills/{name}",
            )

        return ReadinessCheck(name=f"skill {name}", verdict=CheckVerdict.READY, detail=f"installed at {path}")

    def _of_repo(self, repo: str) -> ReadinessCheck:
        if self._forum.can_read(repo=repo):
            return ReadinessCheck(name="repo", verdict=CheckVerdict.READY, detail=f"{repo} is readable")

        return ReadinessCheck(
            name="repo",
            verdict=CheckVerdict.MISSING,
            detail=f"{repo} is not readable",
            fix=f"gh auth login, or ask for access to {repo}",
        )

    def _of_base(self, *, worktree: str, base: str) -> ReadinessCheck:
        behind = self._branches.commits_behind_remote(worktree=worktree, base=base)
        if behind == 0:
            return ReadinessCheck(
                name="base", verdict=CheckVerdict.READY, detail=f"{base} is up to date with its remote"
            )

        return ReadinessCheck(
            name="base",
            verdict=CheckVerdict.WARNING,
            detail=f"{base} is {behind} commit(s) behind its remote",
            fix=f"git -C {worktree} branch -f {base} origin/{base}",
        )
