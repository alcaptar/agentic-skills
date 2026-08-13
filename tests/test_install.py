"""What `make install-skills` leaves behind, run against a throwaway configuration directory.

The deliverable is two halves that install differently: the program is a Python wheel and the rest
is directories Claude Code reads from its configuration directory. Only this half can be measured --
the other one (`install-program`) writes into the machine's environment and does not fit in a suite --
so `install` is split into two targets and this file covers the one that can be.

Three directories are linked and only two of them are skills: `skills/slice-runner/` lost its
`SKILL.md` when the old flow was retired and kept only the helpers `slice-spec` shells out to.

The target is driven with `CLAUDE_HOME=<path>` on the command line rather than the environment
variable it defaults from, because the port that launches processes here carries a cap and takes no
environment.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from conftest import _ROOT

from slice_runner.application.queries.check_readiness import CheckReadiness
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.infrastructure.process import ProcessOutput

_LINKED = ("slice-spec", "deploy-watch", "slice-runner")


def _install_skills(home: Path) -> ProcessOutput:
    """Run the target that only touches the configuration directory, pointed at `home`."""
    return Real.process().run(["make", "install-skills", f"CLAUDE_HOME={home}"], stdin="", cwd=str(_ROOT))


@pytest.mark.integration
def test_installing_points_all_three_linked_directories_at_this_checkout(tmp_path: Path) -> None:
    """All three directories land, and they land as links to the checkout rather than as copies.

    Copies would drift the moment the repo changes, which is the property the symlink exists for:
    editing the repo changes what Claude Code runs, with nothing to re-sync.
    """
    done = _install_skills(tmp_path)

    assert done.code == 0, done.stdout + done.stderr
    for name in _LINKED:
        link = tmp_path / "skills" / name
        assert link.is_symlink(), f"{name} landed as a copy, so editing the repo stops changing what runs"
        assert link.readlink() == _ROOT / "skills" / name


@pytest.mark.integration
def test_installing_the_skills_twice_leaves_the_same_links_and_still_succeeds(tmp_path: Path) -> None:
    """A second run is not an error: an install target that only works once is not an install target."""
    _install_skills(tmp_path)

    done = _install_skills(tmp_path)

    assert done.code == 0, done.stdout + done.stderr
    for name in _LINKED:
        assert (tmp_path / "skills" / name).readlink() == _ROOT / "skills" / name


@pytest.mark.integration
def test_every_helper_slice_spec_invokes_by_absolute_path_is_reachable_after_installing(tmp_path: Path) -> None:
    """The helpers `slice-spec` shells out to resolve under what the installer laid down.

    `slice-spec` invokes its two discovery helpers by absolute path under the configuration
    directory, and they live in `skills/slice-runner/` -- a directory that stopped being a skill when
    the old flow was retired and kept only `scripts/`. While the installer linked just the two real
    skills, a fresh machine got `slice-spec` step 3 with nothing to run: not an error anyone would
    see, but an agent improvising the conventions and the controls instead of discovering them.

    Extracting the paths from the skill rather than listing them here is what makes this a contract:
    a helper invoked from a directory nobody links fails the test instead of failing the person.
    """
    _install_skills(tmp_path)

    invoked = re.findall(r"~/\.claude/(skills/\S+?\.py)", (_ROOT / "skills" / "slice-spec" / "SKILL.md").read_text())

    assert invoked, "slice-spec stopped invoking helpers by absolute path, so this contract needs rewriting"
    for helper in sorted(set(invoked)):
        assert (tmp_path / helper).exists(), f"slice-spec invokes {helper} and the installer leaves it unreachable"


def test_the_doctor_checks_every_helper_slice_spec_invokes_by_absolute_path() -> None:
    """The paths `slice-spec` shells out to are ones `CheckReadiness` names, not just ones the installer lays down.

    Reachability after `make install-skills` is only half of what a fresh machine needs: it says nothing
    until someone actually runs `slice-spec` and step 3 finds no helper to run, silently improvising the
    conventions and the controls instead of discovering them. Extracting the paths from the skill instead
    of listing them here is what makes a helper added to `slice-spec` and forgotten in the doctor fail
    this test instead of a real run.
    """
    invoked = set(
        re.findall(r"~/\.claude/(skills/\S+?\.py)", (_ROOT / "skills" / "slice-spec" / "SKILL.md").read_text())
    )

    assert invoked, "slice-spec stopped invoking helpers by absolute path, so this contract needs rewriting"
    assert invoked == set(CheckReadiness.HELPERS), (
        f"slice-spec invokes {sorted(invoked)} by absolute path and the doctor checks "
        f"{sorted(CheckReadiness.HELPERS)}: a helper missing from the doctor is one whose absence looks "
        "like a working setup"
    )


_LINKED_DECLARATION = re.compile(r"^LINKED\s*:=\s*(.+)$", re.MULTILINE)


def test_the_doctor_checks_every_directory_the_installer_links() -> None:
    """A directory `make install-skills` links and the doctor never looks at is the same gap as an unchecked helper.

    `skills/slice-runner/` carries no `SKILL.md`, so it cannot be checked the way `slice-spec` and
    `deploy-watch` are; the doctor covers it instead through the helpers it holds under `scripts/`.
    Deriving both sides from the Makefile and from `CheckReadiness`, rather than restating the three
    names here, is what makes a fourth linked directory -- or a check quietly dropped -- fail here
    instead of drifting unnoticed.
    """
    declared = _LINKED_DECLARATION.search((_ROOT / "Makefile").read_text())
    assert declared, "Makefile no longer declares LINKED, so this contract has nothing to compare against"
    linked = declared.group(1).split()

    checked_as_a_skill = set(CheckReadiness.SKILLS)
    checked_through_a_helper = {relative.split("/")[1] for relative in CheckReadiness.HELPERS}

    uncovered = [name for name in linked if name not in checked_as_a_skill and name not in checked_through_a_helper]
    assert not uncovered, (
        f"make install-skills links {uncovered}, and the doctor checks it neither as a skill "
        f"({sorted(checked_as_a_skill)}) nor through one of the helpers it holds ({sorted(checked_through_a_helper)})"
    )


@pytest.mark.integration
def test_installing_the_skills_refuses_to_replace_a_link_that_points_somewhere_else(tmp_path: Path) -> None:
    """An occupied link is left untouched and the target fails, naming where it points.

    The real case is a machine where `slice-runner` still points at `agentic-skills-legacy`, from when
    that name was the old flow's skill: silently repointing it would retire a flow someone still uses,
    and the person would find out from the behaviour rather than from the installer.
    """
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    occupied = tmp_path / "skills" / "deploy-watch"
    occupied.parent.mkdir(parents=True)
    occupied.symlink_to(elsewhere)

    done = _install_skills(tmp_path)

    assert done.code != 0, "an occupied link has to stop the install instead of being replaced"
    assert occupied.readlink() == elsewhere
    assert str(occupied) in done.stdout
