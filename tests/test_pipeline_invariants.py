"""Invariants against the tree itself, not two copies of the same prose.

Three of the tests here scan the repo instead of comparing a script to a skill: that no call to an
external process is launched without a cap, that every repo path cited in the docs still exists,
and that the smoke fixture is linted with the same yardstick as the root. `CLAUDE.md` names the
cap on every external call one of the principles the pipeline does not break, and
`docs/conventions/como-se-escribe.md` cites this file as the contract of cited paths. The fourth
test pins what counts as "launching a process" for the cap check, so a scan that only knows
`subprocess.run` cannot pass silently as the whole rule. The fifth scans `conduct_slice.py` for the
same reason: it pins that every call which writes with the harness discards and retries a
`MeasuredCallError`, instead of trusting prose to keep a fourth such call from being added bare.
The sixth pins the fifth's own mechanism: a `self._x.y(...)` the scan has never seen counts as
harness-writing by default, so a step added later on a brand new port turns the suite red instead
of passing by omission the way naming only the three known calls would have.
The seventh scans the whole tracked tree, test tree included, for a role adapter that calls the
harness process on its own instead of through `HarnessInvocationRunner`, the piece that registers
its trace, spend and tool-use. The eighth and ninth pin that mechanism the same way the sixth does:
a shape the scan has never seen, and a path neither exemption list has ever named, both count as
unregistered by default. The tenth pins the seventh's scope: it must reach outside
`src/slice_runner/infrastructure/`, where the rule mostly already holds, or a future narrowing
there would pass by construction instead of by having covered anything. The eleventh guards the
noise list itself against going stale the way `_UNSCANNED` already does above.
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
    "skills/slice-spec/references/observabilidad.md": "documenta rutas de otros repos",
    "playground/tasks": "entrada congelada de un experimento, no se actualiza",
}
"""What is not scanned at all, each for a reason about what the file IS.

`observabilidad.md` is a reference doc about OTHER repos -- every path in it belongs to the tree of
the monitoring library or of the infra repos it documents, not to this one.
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


_CONDUCT_SLICE = "src/slice_runner/application/actions/conduct_slice.py"

_KNOWN_NOT_HARNESS_WRITING = {
    ("_branches", "create"),
    ("_branches", "exists"),
    ("_budgets", "cost_exhausted"),
    ("_budgets", "exhausted"),
    ("_budgets", "wait_exhausted"),
    ("_catch_up", "execute"),
    ("_clock", "sleep"),
    ("_close", "execute"),
    ("_deliver", "execute"),
    ("_deploy_watch", "watch"),
    ("_forum", "any_pull_request"),
    ("_forum", "pull_request_state"),
    ("_machine", "after"),
    ("_prechecks", "execute"),
    ("_pull_request", "body"),
    ("_pull_request", "commit_message"),
    ("_pull_request", "title"),
    ("_read_ci", "execute"),
    ("_read_pull_request", "execute"),
    ("_record_closure", "execute"),
    ("_record_step", "execute"),
    ("_reopen", "execute"),
    ("_repository", "clear_run"),
    ("_repository", "flag_unmerged_pull_request"),
    ("_repository", "pause_for_alignment"),
    ("_repository", "read_understanding"),
    ("_repository", "remove_label"),
    ("_repository", "write_label"),
    ("_repository", "write_malformed_response"),
    ("_repository", "write_precheck_reason"),
    ("_run_controls", "execute"),
    ("_select", "execute"),
    ("_stage", "execute"),
}
"""Every other `self._x.y(...)` call in `conduct_slice.py`, named instead of guessed.

The scan cannot know from the syntax alone whether a brand new `self._x.y(...)` writes with the
harness: that is a fact about the type of `_x`, not about the call site. Naming what does NOT
write with it, instead of what does, is what makes a step added later without this treatment fall
on the unsafe side by default -- the opposite of the allowlist this replaced, which stayed silent
about anything it had never heard of. The cost is this list: a call that is genuinely not
harness-writing but is missing from it is misclassified as one, which only means it must be added
here, not that anything breaks.
"""


def _as_a_harness_writing_call(node: ast.AST) -> tuple[str, str] | None:
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Attribute)
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "self"
    ):
        return None
    pair = (node.func.value.attr, node.func.attr)

    return None if pair in _KNOWN_NOT_HARNESS_WRITING else pair


def _catches_a_measured_call_error(handler: ast.ExceptHandler) -> bool:
    caught = handler.type
    if caught is None:
        return False
    names = caught.elts if isinstance(caught, ast.Tuple) else [caught]

    return any(isinstance(name, ast.Name) and name.id == "MeasuredCallError" for name in names)


def _harness_writing_calls(source: str) -> tuple[int, list[int]]:
    """Every call that writes with the harness, and the lines among them not guarded by a `try`."""
    total = 0
    unguarded: list[int] = []

    def _walk(node: ast.AST, *, guarded: bool) -> None:
        nonlocal total
        if isinstance(node, ast.Call) and _as_a_harness_writing_call(node) is not None:
            total += 1
            if not guarded:
                unguarded.append(node.lineno)
        if isinstance(node, ast.Try):
            body_guarded = guarded or any(_catches_a_measured_call_error(handler) for handler in node.handlers)
            for statement in node.body:
                _walk(statement, guarded=body_guarded)
            for other in (*node.handlers, *node.orelse, *node.finalbody):
                _walk(other, guarded=guarded)
            return
        for descendant in ast.iter_child_nodes(node):
            _walk(descendant, guarded=guarded)

    _walk(ast.parse(source), guarded=False)

    return total, unguarded


def test_no_call_that_writes_with_the_harness_in_conduct_slice_escapes_the_discard_and_retry_treatment() -> None:
    """Understanding a call is discarded the same way implementing and verifying already are.

    A rejection nobody catches does not stop at one call: it kills the whole run before anything is
    written or branched, which is the bug the slice-02 worktree-recovery mechanism exists to undo. The
    total pins the call count too, so a fourth harness-writing call added later without this treatment
    turns the suite red instead of slipping through unnoticed.
    """
    total, unguarded = _harness_writing_calls(_read(_ROOT / _CONDUCT_SLICE))

    assert not unguarded, (
        f"{_CONDUCT_SLICE} calls the harness at line(s) {', '.join(str(line) for line in unguarded)} "
        f"without discarding and retrying a MeasuredCallError, unlike every other harness-writing call"
    )
    assert total == 3, (
        f"{_CONDUCT_SLICE} calls the harness {total} time(s) to write with it, expected exactly 3 "
        f"(understand, implement, verify): a call added or removed here changes what this pins"
    )


def test_a_self_call_not_named_safe_is_treated_as_harness_writing_even_if_the_scan_has_never_seen_it() -> None:
    """The scan cannot tell a new harness-writing step from a new safe one by syntax alone.

    So it does not try: anything on `self` that is not on `_KNOWN_NOT_HARNESS_WRITING` counts as
    harness-writing by default, which is the only way a fourth call added bare -- to a brand new
    port this file has never heard of -- turns the suite red instead of passing by omission, the
    way the three-item allowlist this replaced would have.
    """
    source = "\n".join(
        [
            "class ConductSlice:",
            "    def _implementing(self, progress):",
            "        try:",
            "            self._implement.execute(progress)",
            "        except MeasuredCallError:",
            "            pass",
            "        self._summarize.publish(progress)",
        ]
    )

    assert _harness_writing_calls(source) == (2, [7])


def _launches_something_shaped_like_the_harness(node: ast.Call) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and {"stdin", "cwd"}.issubset({keyword.arg for keyword in node.keywords})
    )


def _harness_shaped_launches(source: str) -> list[int]:
    """Lines calling `something.run(...)` with both `stdin=` and `cwd=`, the shape every call into
    the harness takes -- and also the shape of any other call through this program's `Process`
    port, which is why the exemption lists below exist.
    """
    tree = ast.parse(source)

    return sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _launches_something_shaped_like_the_harness(node)
    )


def test_the_scan_treats_a_role_adapter_shape_it_has_never_seen_as_unregistered_by_default() -> None:
    """Naming what does NOT count, instead of what does, is what makes a role adapter added later
    fall on the unsafe side by default. This source is not in the tree and matches neither
    exemption list, so nothing here recognizes it -- and it is still caught.
    """
    source = "\n".join(
        [
            "class ANewRoleAdapter:",
            "    def act(self):",
            "        return self._harness.run(['claude'], stdin='prompt', cwd='/worktree')",
        ]
    )

    assert _harness_shaped_launches(source) == [3]


def test_a_path_neither_exemption_list_has_ever_named_is_treated_as_unregistered_by_default() -> None:
    """The inversion has two halves: an unseen shape (above) is one, an unseen path is the other.
    Naming what does NOT count, instead of what does, is what makes a role adapter added at a path
    neither list has ever named fall on the unsafe side by default, same as `ANewRoleAdapter` above.
    """
    source = "\n".join(
        [
            "class ANewRoleAdapter:",
            "    def act(self):",
            "        return self._harness.run(['claude'], stdin='prompt', cwd='/worktree')",
        ]
    )

    assert _unregistered_lines("src/slice_runner/infrastructure/a_new_role_adapter.py", source) == [3]


_HARNESS_REGISTRAR = "src/slice_runner/infrastructure/harness_invocation_runner.py"

_HARNESS_SHAPED_LAUNCH_NOISE = {
    "src/slice_runner/infrastructure/local_control_runner.py": "runs lint/tests/types through `sh -c`, not the harness",
    "src/slice_runner/infrastructure/process_source_reader.py": (
        "reads a declared source through `cat`, not the harness"
    ),
    "src/slice_runner/tests/infrastructure/test_local_process.py": (
        "exercises `LocalProcess.run` with a `cwd` on purpose, as a test of that port itself"
    ),
    "src/slice_runner/tests/doubles.py": (
        "doubles the `Process` port and forwards to `Real.process()`, never the harness on its own"
    ),
    "tests/test_install.py": "runs `make install-skills`, not the harness",
    "tests/test_sample_output.py": "runs `ruff` against a copy of the smoke fixture, not the harness",
}
"""Structural noise of the signal, named instead of guessed.

The shape this scan keys on -- a call to `.run(...)` with `stdin=` and `cwd=` together -- is how
every invocation of a subprocess through this program's `Process` port looks, harness or not: it
detects a process, not the harness specifically. There will always be legitimate calls shaped
exactly like the one this exists to catch, so this list does not expire the way the debt list does
-- what grows it is a new legitimate caller of `Process.run`, not a migration.
"""

_HARNESS_SHAPED_LAUNCH_DEBT = {
    "src/slice_runner/infrastructure/claude_deploy_watch.py": (
        "invokes the real harness outside a slice run's cycle -- it runs after the merge, once the "
        "run is already closed and `Step` has no member for that moment -- and its migration onto "
        "HarnessInvocationRunner is slice-03 of this feature (#369)"
    ),
}
"""Consented debt with an expiry, unlike the list above: this entry is a real, unregistered call to
the harness, kept out of this check on purpose until the issue named next to it lands. An entry is
removed when it migrates, never because the scan stopped seeing it.
"""

_SCANNED_FOR_HARNESS_SHAPED_LAUNCHES = _tracked("*.py")

_HARNESS_SHAPED_LAUNCH_EXEMPT = {_HARNESS_REGISTRAR, *_HARNESS_SHAPED_LAUNCH_NOISE, *_HARNESS_SHAPED_LAUNCH_DEBT}


def _unregistered_lines(path: str, source: str) -> list[int]:
    """Lines of `source` shaped like a harness launch, unless `path` is named exempt.

    The exemption check is by path, not by source: a shape the scan has never seen still counts as
    unregistered even at a path that has never been added to either list, which is what the meta-test
    right above exercises without needing a broken tree to prove it.
    """
    return [] if path in _HARNESS_SHAPED_LAUNCH_EXEMPT else _harness_shaped_launches(source)


def test_no_role_adapter_launches_the_harness_process_without_going_through_the_registrar() -> None:
    """`architecture.md`: a business rule is written once, and `HarnessInvocationRunner` is the one
    place that writes the trace, the spend and the tool-use record of a call to the harness.
    Nothing today stops a role adapter from building its own call and skipping that registrar --
    `ClaudeDeployWatch.watch` already does, unmeasured -- so this scans every tracked `.py` file,
    test tree included, for the shape every such call takes.
    """
    unregistered = {
        path: lines
        for path in _SCANNED_FOR_HARNESS_SHAPED_LAUNCHES
        if (lines := _unregistered_lines(path, _read(_ROOT / path)))
    }

    assert not unregistered, (
        "these launch a process shaped like the harness (`stdin=` and `cwd=` together) without going "
        "through HarnessInvocationRunner:\n"
        + "\n".join(
            f"  {path}: line(s) {', '.join(str(line) for line in lines)}"
            for path, lines in sorted(unregistered.items())
        )
    )


_ROLE_ADAPTERS_DIRECTORY = "src/slice_runner/infrastructure/"


def test_the_scans_scope_reaches_launches_outside_where_role_adapters_already_comply() -> None:
    """The scope is the whole tree, test tree included: a check that only ever looked at
    `src/slice_runner/infrastructure/` -- where the rule mostly already holds -- would have
    nothing left to catch outside it and pass by construction, not by having covered anything.
    Every noise entry above lives outside that directory, so this is not hypothetical.
    """
    caught_outside_it = {
        path
        for path in _SCANNED_FOR_HARNESS_SHAPED_LAUNCHES
        if not path.startswith(_ROLE_ADAPTERS_DIRECTORY) and _harness_shaped_launches(_read(_ROOT / path))
    }

    assert caught_outside_it, (
        "no harness-shaped launch exists outside src/slice_runner/infrastructure/, so narrowing the "
        "scan's scope to that directory would pass with nothing left to catch"
    )


def test_every_harness_shaped_launch_noise_entry_still_calls_something_shaped_like_the_harness() -> None:
    """The same liveness check `_UNSCANNED` gets above, applied to this list.

    Without it, a noise entry that stops calling anything shaped like the harness -- because the
    call moved, was renamed, or was removed -- stays exempt forever, and a real unregistered call
    to the harness added at that same path afterwards would pass in silence: exactly the failure
    mode the rest of this file measures.
    """
    for path, reason in _HARNESS_SHAPED_LAUNCH_NOISE.items():
        assert path in _SCANNED_FOR_HARNESS_SHAPED_LAUNCHES, (
            f"the noise entry `{path}` ({reason}) is no longer tracked; drop it from "
            f"_HARNESS_SHAPED_LAUNCH_NOISE instead of leaving a stale exemption"
        )
        assert _harness_shaped_launches(_read(_ROOT / path)), (
            f"the noise entry `{path}` ({reason}) no longer calls anything shaped like the harness; "
            f"drop it from _HARNESS_SHAPED_LAUNCH_NOISE instead of leaving a stale exemption that "
            f"silently widens the check"
        )
