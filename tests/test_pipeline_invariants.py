"""Invariants against the tree itself, not two copies of the same prose.

Three of the tests here scan the repo instead of comparing a script to a skill: that no call to an
external process is launched without a cap, that every repo path cited in the docs still exists,
and that the smoke fixture is linted with the same yardstick as the root. `CLAUDE.md` names the
cap on every external call one of the principles the pipeline does not break, and
`docs/conventions/como-se-escribe.md` cites this file as the contract of cited paths. The fourth
test pins what counts as "launching a process" for the cap check, so a scan that only knows
`subprocess.run` cannot pass silently as the whole rule.
"""

from __future__ import annotations

import ast
import re
import tomllib
from typing import TYPE_CHECKING

import pytest
from conftest import _ROOT, _read, _rel, _tracked

if TYPE_CHECKING:
    from pathlib import Path

_UNSCANNED = {
    "docs/superpowers/specs": "registro fechado, no se actualiza",
    "skills/slice-spec/references/observabilidad.md": "documenta rutas de otros repos",
    "playground/tasks": "entrada congelada de un experimento, no se actualiza",
}
"""Three places are not scanned at all, each for a reason about what the file IS.

`docs/superpowers/specs` holds dated design records: they describe the tree as it was on their
date and are deliberately never updated, so a path they cite going away is correct, not a defect.
`observabilidad.md` is a reference doc about OTHER repos -- every path in it belongs to a
Mercadona tree (mo.pypi.monitoring, mercadona.online.gke), not to this one.
`playground/tasks` holds the frozen input of each experiment: the copies of the conventions a
variant hands to the model are what that run was measured against, so updating them when the tree
moves would destroy the only thing that makes the numbers comparable -- a rerun would no longer be
the same experiment. A path going stale there is the point, not a defect.
"""

_EXEMPT = {
    "tests/test_core.py": "ruta de la fixture de smoke, que la slice crea al correr",
}
"""One token is exempt rather than its whole file.

`smoke/README.md` is worth scanning (it cites `tests/` paths of ours, among others) but it also
speaks in the smoke fixture's own coordinates, and the fixture happens to have a `tests/`
directory just like the repo root.
"""

_BACKTICKED = re.compile(r"`([^`\n]+)`")
_PATHLIKE = re.compile(r"^[\w.][\w./-]*$")
"""What counts as a claim about this repo's tree.

The docs here do not use markdown links for local files; they cite paths in backticks. So the
thing to validate is not `[x](y)` -- there are none -- but every backticked token that claims
something about this tree. A token qualifies only when its first component is a tracked top-level
entry: that keeps bare filenames (`metrics.py`), paths in other repos (`monitoring/metrics.py`),
and branch patterns (`slice/NN-name`) out by construction, instead of by an allowlist that would
have to grow forever.
"""


def _parent_dirs(path: str) -> list[str]:
    parts = path.split("/")[:-1]
    return ["/".join(parts[: index + 1]) for index in range(len(parts))]


def _claimed_repo_paths(markdown: str, top_level: frozenset[str]) -> set[str]:
    """Backticked tokens that read as a path into this repo's tree."""
    claimed = set()
    for raw in _BACKTICKED.findall(markdown):
        token = raw.strip().rstrip("/")
        if not _PATHLIKE.match(token) or "/" not in token:
            continue
        if token.split("/", 1)[0] in top_level:
            claimed.add(token)
    return claimed


@pytest.mark.integration
def test_every_repo_path_cited_in_the_docs_still_exists() -> None:
    """A path in the prose is a claim about the tree, and a rename breaks it silently.

    Not hypothetical: `removed old specs` (fa804ba) deleted nine design docs and left five
    pointers to them in `docs/design-notes.md`, the record we read precisely to avoid
    re-deriving past decisions. Nothing failed, and they stayed dead until this check existed.


    `git ls-files` reads the index, so a doc deleted in the worktree without staging the deletion is still
    listed. Reading it would raise here and bury the real assert under a traceback about the local mess,
    which is not what this test is about.
    """
    tracked = _tracked("*")
    top_level = frozenset(path.split("/", 1)[0] for path in tracked)
    known = set(tracked) | {parent for path in tracked for parent in _parent_dirs(path)}

    for skipped, reason in _UNSCANNED.items():
        assert skipped in known, (
            f"the unscanned entry `{skipped}` ({reason}) is gone; drop it from _UNSCANNED "
            f"instead of leaving a stale exemption that silently widens the check"
        )

    broken: dict[str, list[str]] = {}
    still_cited: set[str] = set()
    for source in _tracked("*.md"):
        if any(source == skip or source.startswith(f"{skip}/") for skip in _UNSCANNED):
            continue
        if not (_ROOT / source).exists():
            continue
        for claimed in _claimed_repo_paths(_read(_ROOT / source), top_level):
            if claimed in _EXEMPT:
                still_cited.add(claimed)
            elif claimed not in known:
                broken.setdefault(claimed, []).append(source)

    assert still_cited == set(_EXEMPT), (
        f"these exemptions are no longer cited anywhere and must be removed: {sorted(set(_EXEMPT) - still_cited)}"
    )
    assert not broken, "the docs cite paths that are not in the tree:\n" + "\n".join(
        f"  {path}  <- cited in {', '.join(sorted(sources))}" for path, sources in sorted(broken.items())
    )


_FIXTURE_PYPROJECT = _ROOT / "smoke" / "fixture" / "pyproject.toml"


def _ruff_lint(path: Path) -> dict[str, object]:
    section = tomllib.loads(_read(path)).get("tool", {}).get("ruff", {}).get("lint", {})
    assert isinstance(section, dict), f"{_rel(path)} has no [tool.ruff.lint] section"

    return section


def _selected_rules(path: Path) -> list[str]:
    selected = _ruff_lint(path).get("select")
    assert isinstance(selected, list), f"{_rel(path)} does not select any ruff rule explicitly"

    return sorted(str(rule) for rule in selected)


def test_the_smoke_fixture_is_linted_with_the_same_yardstick_as_the_repo() -> None:
    """`architecture.md`: "the smoke fixture carries the same `select` as the root. Touch one, touch
    the other", because the fixture is the subject the runner slices in the smoke -- a laxer yardstick
    there "would give the runner a pass that is not worth anything".

    The convention was written and nothing measured it: adding `TID` to the root and forgetting the
    fixture was caught by the judge, not by `make check`. A convention nothing measures does not
    measure anything -- which is the failure this repo already paid for once, in Spanish identifiers.
    """
    root_pyproject = _ROOT / "pyproject.toml"

    assert _selected_rules(root_pyproject) == _selected_rules(_FIXTURE_PYPROJECT), (
        f"the `select` of pyproject.toml and {_rel(_FIXTURE_PYPROJECT)} have diverged: the fixture "
        f"would be measured with a different yardstick than the repo it stands in for"
    )

    root, fixture = _ruff_lint(root_pyproject), _ruff_lint(_FIXTURE_PYPROJECT)
    assert root.get("flake8-tidy-imports") == fixture.get("flake8-tidy-imports"), (
        f"a rule in the `select` is configured differently in {_rel(_FIXTURE_PYPROJECT)}, so the same "
        f"code would pass in one and fail in the other"
    )


_LAUNCHERS = _tracked("src/slice_runner/*.py", "skills/*/scripts/*.py", "smoke/fixture/*.py", "tests/*.py")


_LAUNCHING_CALLS = {
    "subprocess": frozenset({"run", "call", "check_call", "check_output", "Popen"}),
    "os": frozenset({"system", "popen"}),
}
"""Every spelling of "start an external process" in the stdlib this repo could reach for.

`Popen` and `os.system`/`os.popen` take no `timeout` at all, so they have no capped spelling and
always count as uncapped -- which is the point: the cap is not optional here.
"""


def _launches_a_process(node: ast.Call) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.attr in _LAUNCHING_CALLS.get(node.func.value.id, frozenset())
    )


def _uncapped_calls(source: str) -> list[int]:
    """Lines that launch an external process without a `timeout`, which is a call with no cap."""
    tree = ast.parse(source)
    called = (node for node in ast.walk(tree) if isinstance(node, ast.Call))

    return sorted(
        node.lineno
        for node in called
        if _launches_a_process(node) and not any(keyword.arg == "timeout" for keyword in node.keywords)
    )


@pytest.mark.integration
def test_no_call_to_an_external_process_is_launched_without_a_cap() -> None:
    """`CLAUDE.md` says every call to an external process carries a cap per call, and prose is not a cap.

    A call that never comes back hangs the whole run with no diagnosis and no bounded cost, and the
    yardstick that would catch it was written for the skills only, so nobody reviewing the program had
    anything to fail it with -- which is what happened while judging slice-17. The program funnels every
    launch through `LocalProcess`, so one uncapped `subprocess.run` anywhere here is one hole in a rule
    that otherwise holds by construction: this measures the tree instead of trusting the funnel.
    """
    uncapped = {path: lines for path in _LAUNCHERS if (lines := _uncapped_calls(_read(_ROOT / path)))}

    assert not uncapped, "these calls launch a process with no cap on how long it may take:\n" + "\n".join(
        f"  {path}: line(s) {', '.join(str(line) for line in lines)}" for path, lines in sorted(uncapped.items())
    )


def test_the_scan_counts_as_uncapped_every_way_of_launching_a_process_not_only_subprocess_run() -> None:
    """A yardstick that only knows one launcher measures the habit, not the rule.

    `subprocess.run` is what this repo happens to write today, so a scan that keys on it passes a
    `Popen`, a `check_output` or an `os.system` with no cap at all -- and the rule the scan exists to
    enforce says *every* call, not every call written the usual way. `Popen` and `os.system` take no
    `timeout`, so there is no capped spelling of them: they count as uncapped wherever they appear.
    """
    source = "\n".join(
        [
            "import os",
            "import subprocess",
            "subprocess.run(['x'], timeout=1)",
            "subprocess.run(['x'])",
            "subprocess.check_output(['x'])",
            "subprocess.Popen(['x'])",
            "os.system('x')",
        ]
    )

    assert _uncapped_calls(source) == [4, 5, 6, 7]
