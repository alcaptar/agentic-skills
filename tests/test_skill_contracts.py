"""Contract tests over the instruction surface: the markdown IS the product here.

`make check` covers the Python scripts, but the skills themselves are markdown, and every
contract they share with a script -- or with each other -- is currently stated twice. Two
copies drift the moment only one is edited, and nothing fails when they do: the runner keeps
emitting a marker the parser no longer knows, or one half of a deliberately duplicated policy
gets "fixed" on its own. The last test covers a third kind of claim the prose makes and nobody
checks: a path into this repo's own tree.

Each test here extracts a vocabulary from one surface and compares it against the other,
rather than asserting that a given sentence is present. Rewording that keeps both sides in
step passes; changing one side alone fails. That is the only drift these tests exist to catch.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import re
import tomllib
from pathlib import Path

import pytest

import controles
import metrics
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.ci_status import CiStatus
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity
from slice_runner.domain.staged_hygiene import StagedHygiene
from slice_runner.domain.step import Step
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.infrastructure.gh_ci import GhCi
from slice_runner.infrastructure.gh_run_repository import GhRunRepository
from slice_runner.infrastructure.local_skill_library import LocalSkillLibrary
from slice_runner.infrastructure.metrics_invocation import (
    DurableCi,
    DurableDiscardCause,
    DurableVerdict,
    MetricsInvocation,
)
from slice_runner.infrastructure.parent_body import ParentBody
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.infrastructure.slice_verifier_judge import SliceVerifierJudge
from slice_runner.infrastructure.subissue_body import SubissueBody
from slice_runner.infrastructure.verdict_payload import FindingPayload
from slice_runner.tests.doubles import ScriptedProcess
from slice_runner.tests.git_repo import Git
from slice_runner.tests.mothers.closed_slice_mother import ClosedSliceMother

_ROOT = Path(__file__).resolve().parents[1]
_CONTROLES = _ROOT / "skills" / "slice-runner" / "scripts" / "controles.py"
_SPEC = _ROOT / "skills" / "slice-spec" / "SKILL.md"


_PROGRAM_JUDGE = SliceVerifierJudge.adversarial()
"""The judge the PROGRAM builds, which owns its rubric, its tools and what it may read.

`agents/slice-verifier.md` belongs to the old flow (skill + subagent) and stays frozen; the program
owns its judge, so every contract about what the program tells the judge is measured against this.
"""


def _program_rubric() -> str:
    return _PROGRAM_JUDGE.rubric


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rel(path: Path) -> str:
    return str(path.relative_to(_ROOT))


def _tracked(*patterns: str) -> list[str]:
    """Paths git tracks, so the check measures the repo as published, not the local mess.

    Launched through `Git.run` rather than by hand: it is the shared `git` helper of both test trees
    and it carries the cap, which is what keeps this helper from being the one hole in the rule the
    scan below exists to enforce.
    """
    out = Git.run(_ROOT, "ls-files", "-z", "--", *patterns)
    return sorted(p for p in out.split("\0") if p)


def test_every_runstate_closure_the_translator_is_asked_about_returns_a_label_or_none_only_for_merged() -> None:
    """The translator from `RunState` to a GitHub label pays the debt `domain.md` declared.

    `RunState` duplicates, in English, what `issue_body.Estado`/`MotivoBloqueada` already say in
    Spanish, and nothing compared the two sides until the translator that writes to a subissue
    existed. `MERGED` is the one closure with no label on purpose -- GitHub closes the issue itself
    when the pull request merges -- so it is the sole `None` this loop may see; any other closure
    coming back empty is a step the translator forgot to project.
    """
    for state in RunState:
        if state is RunState.OPEN:
            continue
        label = IssueLabel.of(state=state, step=Step.IMPLEMENT)
        if state is RunState.MERGED:
            assert label is None, "MERGED closes the issue on GitHub's side and must carry no label"
        else:
            assert label in set(IssueLabel), f"{state} projects to {label!r}, which is not a label the vocabulary knows"


def test_no_label_in_the_vocabulary_lacks_a_source_in_the_translator_or_a_manual_entry_point() -> None:
    """A manual-source label is not "a person writes it": it is any label that something other
    than `IssueLabel.of` writes, because it happens outside the `(RunState, Step)` pair the
    translator knows about. `PENDING` is the only one: a person writes it by hand when they
    create a subissue (`CLAUDE.md`'s slice). `AWAITING_ALIGNMENT` projects from
    `(RunState.OPEN, Step.UNDERSTAND)` like any other label -- `GhRunRepository.pause_for_alignment`
    still writes it the very first time, before any `Run` exists to project from, but the value it
    writes is the same one the translator already knows for that step. Every other member has to
    come out of some `(RunState, Step)` pair the translator projects, or it is dead vocabulary
    nobody ever writes.
    """
    manual_source = {IssueLabel.PENDING}
    produced = {IssueLabel.of(state=state, step=step) for state in RunState for step in Step} - {None}

    assert set(IssueLabel) - produced == manual_source


_PARENT_EXAMPLE = "### El issue padre"
_SUBISSUE_EXAMPLE = "### Una subissue por slice"
_HARD_RULES = "### Reglas duras"
_AUTHORING_STEPS = "## Steps — modo autoria (por defecto)"
_VALIDATE = "## Steps — modo `validate`"

_SUBISSUE_TITLE = re.compile(r"`(slice-\d+ \([^`)]+\): [^`]+)`")
_KEBAB_TITLE = re.compile(r"^slice-\d\d \((?:[a-z]+: )?[a-z0-9]+(?:-[a-z0-9]+)*\): \S")
_MACRO_LABEL = re.compile(r"`((?:estado|bloqueada|abortada):[a-z-]+)`")
_LABELLED_LINE_WRITTEN = re.compile(r"^([A-Z]{4,})\s*:", re.MULTILINE)
_LABELLED_LINE_NAMED = re.compile(r"`([A-Z]{4,})\s*:")
_CONFIRMATION_ANCHORS = ("spec completa", "espera confirmacion")
"""Short anchors for the gate criterion, which has no second surface to compare against.

`slice-spec` creates issues in someone else's repository, so the gate -- print everything and wait --
is the whole safety of the step. Nothing else in the tree states it, so this is a claim about the
prose rather than a comparison; reword the sentence and the anchors move with it.
"""

_VALIDATE_ANCHORS = (
    "la regla que incumple y su ubicacion",
    "issue padre",
    "slice-NN (#numero)",
    "en el titulo, en la etiqueta o en el cuerpo",
)
"""Same kind of claim as `_CONFIRMATION_ANCHORS`, for the other half of what `validate` owes.

Checking the new shape is measured by comparing vocabularies; *reporting* each deviation with its rule
and its location is prose, and there is no second surface to compare it against -- the location is only
useful to the person reading the report. It is not decoration either: with the spec split across a
parent and twelve subissues, a deviation without its location is one the person has to go and find.
Nothing else in the tree states it, so the anchors travel with the sentence.
"""

_SUBISSUE_LINES = frozenset({"REPO", "INTENCION", "ACEPTACION", "SENAL"})
"""The four labelled lines a subissue body carries, written down instead of derived from the example.

Only one of them has a consumer in the program: `REPO:`, which `SubissueBody` reads, and which the test
above measures against it. Nothing in production reads `INTENCION:`, `ACEPTACION:` or `SENAL:` yet --
they travel as prose to the implementer and to `deploy-watch` -- so there is no second surface to
compare the set against, and deriving it from the very example under test approves whatever the example
happens to say: drop `SENAL:` from the three regions at once and all three sets still match. So the set
is an external claim about the prose, with its reason next to it, like `_CONFIRMATION_ANCHORS`.
"""


def _without_fences(markdown: str) -> str:
    return re.sub(r"^```.*?^```\n", "", markdown, flags=re.DOTALL | re.MULTILINE)


def _spec_example(heading: str) -> str:
    """The fenced example a section of `slice-spec` carries, taken from the file, not restated here.

    Read from the raw text on purpose: the parent's example contains `##` lines of its own, so
    cutting the section by headings first would truncate it at the format it is documenting.
    """
    text = _read(_SPEC)
    at = text.find(f"\n{heading}\n")
    assert at != -1, f"cannot find `{heading}` in {_rel(_SPEC)}"

    block = re.search(r"```markdown\n(.*?)^```", text[at:], re.DOTALL | re.MULTILINE)
    assert block, f"`{heading}` in {_rel(_SPEC)} carries no fenced example"

    return block.group(1)


def _spec_prose(heading: str) -> str:
    """The prose of a section, fenced examples removed, so a rule is read from the rule."""
    stripped = _without_fences(_read(_SPEC))
    at = stripped.find(f"\n{heading}\n")
    assert at != -1, f"cannot find `{heading}` in {_rel(_SPEC)}"

    body = stripped[at + len(heading) + 2 :]
    end = re.search(r"^#{2,4} ", body, re.MULTILINE)

    return body[: end.start()] if end else body


def test_the_parent_issue_slice_spec_documents_is_one_the_program_reads_whole() -> None:
    """The parent carries the intention, the yardstick and the commands, and `ParentBody` is what reads it.

    The example in the skill is what a model imitates, so it is the real contract: a heading renamed on
    one side alone gives a parent the program parses as empty, and `Prechecks` then refuses to run a
    perfectly written spec -- or, worse, runs it with no yardstick. Parsing the documented example is
    the only way to measure that the two sides still agree.
    """
    parsed = ParentBody.parse(_spec_example(_PARENT_EXAMPLE), repo=None)

    assert parsed.intention, "the documented parent carries no `## Intencion` the program can read"
    assert parsed.sources, "the documented parent carries no source the program can read"
    assert parsed.controls.commands, "the documented parent carries no control command the program can read"


def test_the_exemption_line_slice_spec_documents_is_read_as_an_exemption_and_never_as_a_command() -> None:
    """`- ninguno: <motivo>` declares that a repo has no controls; it is not a control called `ninguno`.

    It used to come out of the parser as `ControlCommand(name="ninguno", command=<the reason>)`, which
    means whoever runs the controls would hand a sentence of Spanish prose to a shell. Empty and exempt
    still are not the same thing: with no controls and no exemption the prechecks fail closed, and a
    declared exemption is treated as an exempt layer with nothing to run. The target repo comes out of
    the subissue example, so this also pins that a slice with `REPO:` has the subsection of its repo.
    """
    target = SubissueBody.parse(_spec_example(_SUBISSUE_EXAMPLE)).repo
    assert target, "the documented subissue carries no `REPO:`, so there is no target repo to filter by"

    controls = ParentBody.parse(_spec_example(_PARENT_EXAMPLE), repo=target).controls

    assert controls.declared, f"the documented parent declares nothing for {target}, which fails closed"
    assert controls.exemption_reason, f"the exemption the parent documents for {target} carries no reason"
    assert controls.commands == (), (
        f"the exemption line documented for {target} came back as {controls.commands}: a reason for "
        f"having no controls has become a command someone would try to execute"
    )


def _documented_subissue_title() -> str:
    titles: list[str] = _SUBISSUE_TITLE.findall(_spec_prose(_SUBISSUE_EXAMPLE))
    assert len(titles) == 1, f"expected exactly one subissue title under `{_SUBISSUE_EXAMPLE}`, found {titles}"

    return titles[0]


def test_the_subissue_slice_spec_documents_is_read_by_the_program_as_the_slice_it_names() -> None:
    """Title, label and body of the documented subissue, read by the program that consumes them.

    The identifier in the title is what orders the slices -- `GhRunRepository` sorts by it and rejects a
    title without it -- and the name is what derives the branch and the commit scope, so it has to be
    kebab-case. The macro state arrives as a label, not as a marker in the text. And the execution state
    block is absent: it belongs to the machine, so a documented body that already carried one would have
    the skill writing a run that never happened.

    The four labelled lines are asserted, not just `REPO:`, because all four now have a consumer: the
    intention, the criteria and the signal travel into the prompts of the implementer and of the judge.
    Parsing them is fail-soft by design -- a line the parser does not recognise is not an error, it is an
    empty field -- so a rename on one side alone would leave both agents working with an empty yardstick
    and nothing at all would break. `_SUBISSUE_LINES` already claims the example writes the four; this is
    what checks the program reads the four.
    """
    title = _documented_subissue_title()
    label = {"id": "LA_kwDOThEBoM8AAAACu6gVcw", "name": IssueLabel.PENDING.value, "description": "", "color": "5319e7"}
    recorded = [
        {
            "number": 44,
            "title": title,
            "body": _spec_example(_SUBISSUE_EXAMPLE),
            "labels": [label],
            "state": "OPEN",
        }
    ]
    process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(recorded), stderr=""))

    children = GhRunRepository(process=process).read_children(repo="alcaptar/agentic-skills", parent=43, expected=1)

    assert _KEBAB_TITLE.match(title), f"the documented title {title!r} does not carry `slice-NN (name-kebab):`"
    assert children[0].slice_id == title.split(" ", 1)[0]
    assert children[0].repo, "the documented subissue carries no target repo the program can read"
    assert children[0].intention, "the documented subissue carries no `INTENCION:` the program can read"
    assert children[0].criteria, "the documented subissue carries no `ACEPTACION:` the program can read"
    assert children[0].signal, "the documented subissue carries no `SENAL:` the program can read"
    assert children[0].label is IssueLabel.PENDING
    assert children[0].run is None, (
        "the documented subissue body already carries an execution state block, which is the machine's"
    )


def test_the_labelled_lines_of_a_subissue_are_the_same_in_the_example_the_rules_and_the_validate_checklist() -> None:
    """Three surfaces of one contract, all inside `slice-spec`: what it shows, demands and checks.

    The example is what a model copies, the rules are what it is told, and `validate` is what catches a
    spec that does not comply. A label added to the rules but not to the example is written by nobody; a
    label in the example that `validate` does not know is one whose absence is approved as valid, which
    is the failure mode that makes the mode worthless. The set the three are held to is
    `_SUBISSUE_LINES` and not the example itself: derived from the example, the three could agree on
    dropping one and nothing would notice.
    """
    written = set(_LABELLED_LINE_WRITTEN.findall(_spec_example(_SUBISSUE_EXAMPLE)))
    assert written == _SUBISSUE_LINES, (
        f"the example under `{_SUBISSUE_EXAMPLE}` writes {sorted(written)}, and a subissue body carries "
        f"{sorted(_SUBISSUE_LINES)}: the intention, the criteria, the signal and the target repo"
    )

    demanded = set(_LABELLED_LINE_NAMED.findall(_spec_prose(_HARD_RULES)))
    checked = set(_LABELLED_LINE_NAMED.findall(_spec_prose(_VALIDATE)))

    assert demanded == written, (
        f"the example and the hard rules of {_rel(_SPEC)} disagree on the lines of a subissue: "
        f"only in the rules {sorted(demanded - written)}, only in the example {sorted(written - demanded)}"
    )
    assert checked == written, (
        f"the example and the validate checklist of {_rel(_SPEC)} disagree on the lines of a subissue: "
        f"only in validate {sorted(checked - written)}, only in the example {sorted(written - checked)}"
    )


def test_the_macro_state_slice_spec_writes_is_a_label_of_the_vocabulary_and_never_a_marker_in_the_text() -> None:
    """The state moved out of the prose and into a GitHub label, and both halves need measuring.

    A label the skill invents is one nothing reads -- `GhRunRepository` only recognises members of
    `IssueLabel` and returns `None` for anything else, so an invented one reads as "no state at all".
    The markers are the other half: as long as the checkbox and the `[estado]` marker survive anywhere
    in the skill, a model has two ways to write the state and only one of them is read.
    """
    documented = set(_MACRO_LABEL.findall(_read(_SPEC)))
    assert documented, f"{_rel(_SPEC)} names no macro state label at all"

    unknown = sorted(documented - set(IssueLabel))
    assert not unknown, f"{_rel(_SPEC)} names {unknown}, which `IssueLabel` does not know and nothing reads"
    assert IssueLabel.PENDING.value in documented, (
        f"{_rel(_SPEC)} no longer names {IssueLabel.PENDING.value}, the state every slice starts in"
    )

    text = _read(_SPEC)
    leftovers = [marker for marker in ("- [ ]", "- [x]", "[pendiente]", "[en-curso]") if marker in text]
    assert not leftovers, (
        f"{_rel(_SPEC)} still writes {leftovers}: the state of a slice is a label, and a marker in the "
        f"text is a second place to write it that nothing reads"
    )


def test_the_step_that_creates_the_issues_shows_the_whole_spec_and_waits_before_creating_anything() -> None:
    """Creating the tree is the one irreversible thing this skill does, and it does it in someone's repo.

    A parent plus one subissue per slice, each with `--parent` -- that flag is what makes them children,
    and the program finds them with `parent-issue:<repo>#<n>`, so a subissue created without it is
    invisible to the run -- and with `--label`, because the state is a label from the moment it is
    created. Before any of that, the whole spec goes to the terminal and the step waits: there is no
    other artifact to review, since the spec no longer exists as a file anybody can read.
    """
    steps = re.split(r"^(?=\d+[a-z]?\.\s)", _spec_prose(_AUTHORING_STEPS), flags=re.MULTILINE)
    creating = [step for step in steps if "gh issue create" in step]
    assert len(creating) == 1, f"expected exactly one step of {_rel(_SPEC)} to create issues, found {len(creating)}"

    step = creating[0]
    for flag in ("--parent", "--label"):
        assert flag in step, f"the creating step of {_rel(_SPEC)} does not pass {flag}"

    missing = [anchor for anchor in _CONFIRMATION_ANCHORS if anchor not in step]
    assert not missing, (
        f"the creating step of {_rel(_SPEC)} no longer states {missing}: nothing else in the tree says "
        f"that the spec is shown whole and confirmed before anything is created"
    )


def test_the_validate_mode_reports_every_deviation_with_its_rule_and_where_it_lives() -> None:
    """The other half of what `validate` owes, and the one that only exists as prose.

    Checking the new shape is measured by comparing vocabularies; reporting is not, and a mode that
    finds a deviation and does not say where it is leaves the person searching a parent plus one
    subissue per slice. The locations are the artifacts themselves -- the parent's body, or a subissue
    named by its identifier and number, and within it the title, the label or the body -- so this is a
    claim about the paragraph, whitespace normalised so rewrapping a line is free.
    """
    prose = " ".join(_spec_prose(_VALIDATE).split())

    missing = [anchor for anchor in _VALIDATE_ANCHORS if anchor not in prose]
    assert not missing, (
        f"the `validate` mode of {_rel(_SPEC)} no longer states {missing}: a deviation reported without "
        f"its rule and its location is one the person has to go and find"
    )


_CI_STATES_PAIRED = {
    CiStatus.GREEN: controles.EstadoCI.VERDE,
    CiStatus.RED: controles.EstadoCI.ROJO,
    CiStatus.PENDING: controles.EstadoCI.PENDIENTE,
    CiStatus.NO_CHECKS: controles.EstadoCI.SIN_CHECKS,
    CiStatus.UNKNOWN: controles.EstadoCI.DESCONOCIDO,
}
"""The one thing about this duplicate that cannot be derived: which member means which.

The program spells the states in English and the script in Spanish, so comparing the two sets of
strings would put `green` against `verde` and fail on a contract in perfect health. What is written
down here is the meaning, once, and both vocabularies are then held to it: a state added or dropped on
one side alone breaks, and adding one to both costs declaring its pair, which is what a translated
duplicate is worth.
"""


def test_the_ci_states_the_program_knows_are_the_ones_the_script_classifies() -> None:
    """`CiStatus` is the third declared copy of a vocabulary of `skills/`, and nothing measured it.

    `docs/conventions/domain.md` declares it beside `RunState` and `StagedHygiene.FORBIDDEN_PREFIXES`:
    the program imports nothing from `skills/`, so the classifier of `gh pr checks` exists twice. The
    other two copies are measured and this one was not. Each of the five is a branch the run takes with
    its pull request already open -- `pendiente` waits, `rojo` closes blocked, and `desconocido` and
    `sin-checks` are the two ways of not being able to affirm a green -- so a state present on one side
    only is either a branch nothing produces or a result nobody has a rule for.
    """
    assert set(_CI_STATES_PAIRED) == set(CiStatus), (
        f"CiStatus and the pairing it is held to disagree: "
        f"only in the program {sorted(set(CiStatus) - set(_CI_STATES_PAIRED))}, "
        f"only in the pairing {sorted(set(_CI_STATES_PAIRED) - set(CiStatus))}"
    )
    assert set(_CI_STATES_PAIRED.values()) == set(controles.EstadoCI), (
        f"controles.EstadoCI and the pairing it is held to disagree: "
        f"only in the script {sorted(set(controles.EstadoCI) - set(_CI_STATES_PAIRED.values()))}, "
        f"only in the pairing {sorted(set(_CI_STATES_PAIRED.values()) - set(controles.EstadoCI))}"
    )


def test_the_ci_buckets_the_program_classifies_are_the_ones_the_script_classifies() -> None:
    """The same duplicate one layer down, on strings neither side gets to choose.

    Unlike the states, the buckets are `gh pr checks`'s own vocabulary, so both copies spell them
    identically and the sets compare directly. They are what the fail-closed order is built on: a
    bucket outside the known set is `desconocido` and never green, so one taught to a single copy would
    make the same pull request green or not depending on which flow asked.
    """
    duplicated = {
        "_CI_BUCKETS_ROJO": (GhCi.RED_BUCKETS, controles._CI_BUCKETS_ROJO),
        "_CI_BUCKETS_OK": (GhCi.OK_BUCKETS, controles._CI_BUCKETS_OK),
        "_CI_BUCKETS": (GhCi.KNOWN_BUCKETS, controles._CI_BUCKETS),
    }

    for named, (program, script) in duplicated.items():
        assert program == script, (
            f"GhCi and controles.{named} disagree on the buckets of `gh pr checks`: "
            f"only in the program {sorted(program - script)}, only in the script {sorted(script - program)}"
        )


_GRACE_WINDOW_IS_WRITTEN_IN = (
    _CONTROLES,
    _ROOT / "docs" / "design-notes.md",
    _ROOT / "README.md",
)


def _grace_window(text: str) -> tuple[int, int]:
    """The two numbers of the grace window as some surface writes them: ticks and seconds."""
    ticks = re.search(r"(\d+)\s+ticks\s+indeterminados", text)
    assert ticks, "the grace window is stated without how many ticks it takes"
    seconds = re.search(r"(\d+)\s+s\s+o\s+mas\s+entre\s+tick\s+y\s+tick", text)
    assert seconds, "the grace window is stated without how long a tick waits"

    return int(ticks.group(1)), int(seconds.group(1))


def test_the_grace_window_is_the_same_number_wherever_it_is_written() -> None:
    """`CLAUDE.md` calls this a declared duplicate, and until now nothing measured it.

    The number lived in two places on purpose -- step 9 of the old skill-driven runner, which
    counted the ticks, and the docstring of `ci-status`, which explains why its exit code 4 is
    one of them -- and it grew from there as the program took over: the count now lives in
    `Budgets`, which is what decides when the window is spent, and the surfaces left in prose are
    the ones this test still holds to that number. Copies of a policy number with no test is how a
    run closes `bloqueada: ci-indeterminada` after one tick while the prose still promises three.
    Every surface that states the number is in here: a copy left out is measured by nothing, which
    is the state this test exists to end.
    """
    budgets = Budgets()
    written = {_rel(path): _grace_window(_read(path)) for path in _GRACE_WINDOW_IS_WRITTEN_IN}

    assert set(written.values()) == {(budgets.indeterminate_ticks, budgets.seconds_between_ticks)}, (
        f"the grace window of {type(budgets).__name__} is "
        f"{(budgets.indeterminate_ticks, budgets.seconds_between_ticks)} and the prose writes {written}"
    )


def test_the_forbidden_artifacts_are_the_same_ones_in_the_script_and_in_the_program() -> None:
    """The hygiene backstop is written twice on purpose, and until now nothing measured it.

    `controles.FORBIDDEN_PREFIXES` is what the old flow's `pr-hygiene` control enforces, and
    `StagedHygiene.FORBIDDEN_PREFIXES` is what the program enforces when it stages. The program
    imports nothing from `skills/` -- the argument is in `docs/conventions/infrastructure.md` --
    so the duplication is the decision. What is not allowed is one copy gaining a prefix the
    other does not: the same artifact would then enter the pull request or not depending on who
    opened it.
    """
    script = set(controles.FORBIDDEN_PREFIXES)
    program = set(StagedHygiene.FORBIDDEN_PREFIXES)

    assert script == program, (
        "controles.FORBIDDEN_PREFIXES y StagedHygiene.FORBIDDEN_PREFIXES no prohiben lo mismo: "
        f"solo en el script {sorted(script - program)}, solo en el programa {sorted(program - script)}"
    )


def test_the_durable_vocabulary_the_program_writes_is_the_one_the_metrics_cli_accepts() -> None:
    """The program shells out to `metrics.py` instead of importing it, so both spell the vocabulary.

    That duplication is the declared decision of `docs/conventions/infrastructure.md` -- the program
    imports nothing from `skills/` -- and a declared duplication that nobody measures is drift with a
    docstring. Adding a member on one side only turns the closing step of a run into an argparse
    error, at the exact moment a failure loses the row outright.
    """
    duplicated = {
        "veredicto": ({str(v) for v in DurableVerdict}, {str(v) for v in metrics.Veredicto}),
        "ci": ({str(c) for c in DurableCi}, {str(c) for c in metrics.Ci}),
        "descartes_verify_causa": (
            {str(c) for c in DurableDiscardCause},
            {str(c) for c in metrics.CausaDescarte},
        ),
    }

    for field, (program, script) in duplicated.items():
        assert program == script, (
            f"the program and metrics.py disagree on the `{field}` of the durable log: "
            f"only in the program {sorted(program - script)}, only in the script {sorted(script - program)}"
        )


def test_the_record_the_program_builds_is_one_the_metrics_cli_accepts(tmp_path: Path) -> None:
    """The flags travel as an argv, so a rename on either side only shows up when a slice closes.

    The first two entries of the invocation are the interpreter and the resolved path of the script,
    which is what a subprocess needs and what `main` must not see; `--path` goes last so the assert
    reads a throwaway log instead of the real durable one.
    """
    closed = ClosedSliceMother.merged_discarding_because_of(DiscardCause.FAILED_CALL)
    log = tmp_path / "metrics.jsonl"

    assert metrics.main([*MetricsInvocation(closed=closed).argv[2:], "--path", str(log)]) == 0

    row = json.loads(log.read_text(encoding="utf-8").strip())
    assert row["harness"] == {
        "coste_usd": closed.spend.cost_usd,
        "turnos": closed.spend.turns,
        "duracion_ms": closed.spend.duration_ms,
        "tokens_cache": closed.spend.cache_read_tokens,
    }
    assert row["modelos"] == list(closed.spend.models)
    assert row["variante"] == MetricsInvocation.VARIANT
    assert row["descartes_verify_causa"] == str(DurableDiscardCause.FAILED_CALL)


def _json_shape(value: object) -> object:
    """Structural skeleton of a parsed JSON value: keys and scalar types, no example data.

    Comparing shapes rather than text makes the check insensitive to reformatting, key order,
    and changes to the illustrative values, while still catching a renamed, added, or dropped
    field -- which is the only thing that would actually break the orchestrator's parsing.
    """
    if isinstance(value, dict):
        return {key: _json_shape(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_json_shape(item) for item in value]
    return type(value).__name__


def _sole_json_block_in(markdown: str, *, where: str = "the program's rubric") -> object:
    blocks = re.findall(r"```json\n(.*?)```", markdown, re.DOTALL)
    assert len(blocks) == 1, f"expected exactly one ```json block in {where}, found {len(blocks)}"
    return json.loads(blocks[0])


def _granted_tools() -> set[str]:
    return set(_PROGRAM_JUDGE.tools)


def test_the_program_does_not_grant_the_judge_what_its_own_rubric_says_he_does_not_have() -> None:
    """The rubric tells the judge it has no `Bash`, "a proposito", and builds three items on that.

    It is what stops it from trying to run lint or tests, and what justifies handing it the diff
    already computed. Granting `Bash` would make the rubric a lie the judge reads first, and the judge
    would have no way to know which half is true. The old flow enforces the same thing structurally,
    through the `tools:` header of `agents/slice-verifier.md`; the program has no header, so this is
    where it gets enforced.
    """
    rubric = _program_rubric()
    assert "No tienes `Bash`" in rubric, (
        "the program's rubric no longer tells the judge it has no `Bash`; either restore it or stop "
        "building the 'you do not run anything' items on a premise that is not stated"
    )

    assert "Bash" not in _granted_tools(), (
        f"the argv grants {sorted(_granted_tools())}, and its own rubric tells the judge it has no `Bash`"
    )


_SKILL_ORDER_RE = re.compile(r"(?:corre|carga)[^.]*?`([a-z][a-z0-9-]{4,})`", re.IGNORECASE)


def _skills_the_rubric_orders() -> set[str]:
    """The skills the rubric tells the judge to load, taken from the rubric itself."""
    return set(_SKILL_ORDER_RE.findall(_program_rubric()))


def test_every_skill_the_rubric_orders_is_one_the_judge_can_actually_load() -> None:
    """The whole invariant in one place: ordered skill -> `Skill` granted -> and reachable.

    It used to be two contracts measuring halves -- one that `Skill` is granted, one that the rubric
    does not promise a file that is not there -- and neither caught the real hole: the rubric ordered
    two skills whose `references/` sat outside every granted directory, so items 1 and 8 were judged
    with no yardstick and the verdict came back just as clean. Measured live: without the grant the
    envelope carries `permission_denials` and the judge answers that it has no permission.

    That hole is why `Judge` exists as one object. This is the test that object makes possible.

    Reachability needs a machine that has the library, so it is skipped where there is none (the
    continuous integration runner has no `~/.claude`); what always runs is the tools half.
    """
    ordered = _skills_the_rubric_orders()
    assert ordered, (
        "no skill is ordered anywhere in the program's rubric. Either the items that loaded one are "
        "gone -- and then `Skill` should stop being granted -- or the sentence changed shape and this "
        "contract stopped measuring anything"
    )

    assert "Skill" in _granted_tools(), (
        f"the rubric orders {sorted(ordered)} but the judge is granted only {sorted(_granted_tools())}"
    )

    trees = LocalSkillLibrary().directories()
    if not trees:
        pytest.skip("this machine has no skill library, so reachability cannot be measured from here")

    unreachable = sorted(name for name in ordered if not _somewhere_under(trees, name))
    assert not unreachable, (
        f"the rubric orders {unreachable}, the judge is granted {[str(tree) for tree in trees]}, and "
        f"nothing under them is named like that: those items would be judged with an empty yardstick"
    )


def _somewhere_under(trees: tuple[Path, ...], name: str) -> bool:
    return any(next(tree.rglob(name), None) is not None for tree in trees)


def _diff_bullet() -> str:
    """The rubric's own description of the diff it hands the judge."""
    bullet = re.search(
        r"^- \*\*El diff completo de la slice\*\*(.*?)(?=^- \*\*)", _program_rubric(), re.DOTALL | re.MULTILINE
    )
    assert bullet, "cannot find the diff bullet in the program's rubric"
    return bullet.group(1)


def test_the_rubric_does_not_promise_a_file_the_program_no_longer_writes() -> None:
    """The diff travels inside the prompt, so `slice.diff` is a path that no longer exists.

    A rubric that still named it would send the judge to open a file that was never written -- and
    the judge has `Read`, so it would fail silently rather than loudly, and then judge whatever it
    could reach instead. That failure mode is exactly why the diff moved into the prompt: what is
    already in front of the judge cannot be skipped. `GitDiffReader` writing nothing is pinned in
    `src/slice_runner/tests/infrastructure/test_git_diff_reader.py`; this guards the prose.
    """
    assert "slice.diff" not in _program_rubric(), (
        "the program's rubric still names `slice.diff`, but the program writes no patch: the diff "
        "travels inside the prompt. Either the file came back or the sentence has to go"
    )


def test_the_rubric_describes_the_diff_range_the_program_actually_produces() -> None:
    """The rubric told the judge the diff was `<base>...HEAD` while the script diffs the index.

    It was true once and stopped being true when the range moved to `--cached --merge-base`, for a
        reason recorded in `docs/conventions/infrastructure.md`: the commit happens after verification, so
        against `HEAD` there would be nothing to see. Nobody updated the sentence that travels to the judge,
        and nothing measured it -- the other contract tests here compare closed vocabularies, not prose
        describing a git range. The range is now produced by `GitDiffReader`, whose behaviour is pinned in
        `src/slice_runner/tests/infrastructure/test_git_diff_reader.py`.

        A false premise about what it is looking at is how a judge produces confidently wrong findings:
        expecting commits, or reasoning about history that is not in the range.

        This test guards the sentence only; the behaviour is pinned by the reader's own tests.
    """
    bullet = _diff_bullet()

    assert "..HEAD" not in bullet, (
        "the program's rubric describes the diff as a range ending at `HEAD`, but `GitDiffReader` "
        "diffs the staged index against the branch-point. The judge would be told it looks at committed "
        "history when it looks at the index"
    )
    assert "indice" in bullet.lower(), (
        "the program's rubric no longer tells the judge that the diff is the index. Omitting it is "
        "not enough: the judge has to know it is looking at what the commit will be, not at history"
    )


def _documented_finding() -> dict[str, object]:
    """The single example finding in the rubric, which is where the verdict's fields are stated."""
    schema = _sole_json_block_in(_program_rubric())
    assert isinstance(schema, dict)
    hallazgos = schema["hallazgos"]
    assert isinstance(hallazgos, list)
    assert hallazgos
    primero = hallazgos[0]
    assert isinstance(primero, dict)
    return primero


def test_the_finding_keys_in_the_rubric_are_the_ones_the_program_maps_its_fields_to() -> None:
    """The rubric states the finding's keys; the program's fields reach them through one mapping.

    A key documented but not aliased is dropped on the way in -- silently, because the JSON schema
    the program sends is generated from those same aliases, so the judge is never even asked for it.
    The reverse makes the program demand a key the rubric never told the judge to emit.
    """
    documented = set(_documented_finding())

    mapped = FindingPayload.contract_keys()
    assert documented == mapped, (
        f"the finding in the program's rubric and the aliases of `FindingPayload` disagree: "
        f"only in the rubric {sorted(documented - mapped)}, only in the program {sorted(mapped - documented)}"
    )


def test_the_verdicts_and_severities_in_the_rubric_are_the_ones_the_program_accepts() -> None:
    """Same drift, on the two closed vocabularies.

    These reach the judge as `enum` values in `--json-schema`, so a level in the rubric that the
    program does not know is one the judge is forbidden from emitting -- and one the program knows
    but the rubric does not document is dead vocabulary nobody will ever produce.
    """
    schema = _sole_json_block_in(_program_rubric())
    assert isinstance(schema, dict)

    assert {v.strip() for v in str(schema["veredicto"]).split("|")} == set(Ruling)
    assert {s.strip() for s in str(_documented_finding()["severidad"]).split("|")} == set(Severity)


def test_every_subcommand_of_both_scripts_accepts_json() -> None:
    """One rule across both scripts: human-readable by default, `--json` for structured.

    This is not tidiness. `issue_body.py show` used to emit JSON unconditionally and take
    `--pretty`, while the five `controles.py` subcommands are human-readable unless given
    `--json` -- and during the 2026-07-30 probe that difference tripped the person who had
    written both scripts the day before. Two scripts in one repo with opposite conventions
    for the same thing is a trap, so the rule is now enforced instead of remembered.
    """
    for script in ("controles", "issue_body"):
        module = importlib.import_module(script)
        subcommands = _subcommand_parsers(module.build_parser())
        assert subcommands, f"{script}.py exposes no subcommands"
        for name, subparser in sorted(subcommands.items()):
            usage = subparser.format_usage()
            assert "--json" in usage, (
                f"{script}.py {name} does not accept --json; every subcommand of both "
                f"scripts must, so the flag never depends on remembering which script it is"
            )
            assert "--pretty" not in usage, (
                f"{script}.py {name} still has --pretty, the flag the inconsistency came from"
            )


def _subcommand_parsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    """Subparsers by name, coupling to as little of `argparse` as the task allows.

    `argparse` publishes no API for walking back into its subparsers, so `_actions` is
    unavoidable. What it does avoid is naming `argparse._SubParsersAction`: the action is
    identified by its documented `choices` attribute instead of by a private class, and the flags
    of each subcommand are then read from the public `format_usage()`. One private instead of
    three, in a test whose subject is our own convention and not CPython's internals.
    """
    for action in parser._actions:
        choices = action.choices
        if isinstance(choices, dict) and all(isinstance(sub, argparse.ArgumentParser) for sub in choices.values()):
            return dict(choices)
    return {}


_UNSCANNED = {
    "docs/superpowers/specs": "registro fechado, no se actualiza",
    "skills/slice-spec/references/observabilidad.md": "documenta rutas de otros repos",
}
"""Two files are not scanned at all, each for a reason about what the file IS.

`docs/superpowers/specs` holds dated design records: they describe the tree as it was on their
date and are deliberately never updated, so a path they cite going away is correct, not a defect.
`observabilidad.md` is a reference doc about OTHER repos -- every path in it belongs to a
Mercadona tree (mo.pypi.monitoring, mercadona.online.gke), not to this one.
"""

_EXEMPT = {
    "tests/test_core.py": "ruta de la fixture de smoke, que la slice crea al correr",
}
"""One token is exempt rather than its whole file.

`smoke/README.md` is worth scanning (it cites agents/ and tests/ paths of ours) but it also
speaks in the smoke fixture's own coordinates, and the fixture happens to have a `tests/`
directory just like the repo root.
"""

_BACKTICKED = re.compile(r"`([^`\n]+)`")
_PATHLIKE = re.compile(r"^[\w.][\w./-]*$")
"""What counts as a claim about this repo's tree.

The docs here do not use markdown links for local files; they cite paths in backticks. So the
thing to validate is not `[x](y)` -- there are none -- but every backticked token that claims
something about this tree. A token qualifies only when its first component is a tracked top-level
entry: that keeps bare filenames (`controles.py`), paths in other repos (`monitoring/metrics.py`),
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


_README = _ROOT / "README.md"

_LAUNCH = re.compile(r"uv run ([\w.-]+)(?= (?:verify|explain|run)\b)")
_CONSOLE_SCRIPT = re.compile(r"^\[project\.scripts\]\s*\n([\w-]+) *=", re.MULTILINE)
_STALE_LAUNCH = re.compile(r"[^\n`|]*PYTHONPATH=src[^\n`|]*slice_runner[^\n`|]*")
_LAUNCH_SOURCES = ["README.md", "pyproject.toml", *_tracked("docs/conventions/*.md")]


@pytest.mark.integration
def test_every_documented_way_to_launch_the_program_names_the_installed_executable() -> None:
    """The name of the executable is written in `[project.scripts]` and in every doc that says how to launch it.

    This used to measure something else: while `package = false` the program was not installed and a
    plain `python -m` did not find it, so the contract was that every documented invocation carried
    `PYTHONPATH=src`. The slice of the conductor installs the executable and that premise dies; what
    still holds is the same failure mode with another face -- renaming the script of `[project.scripts]`
    leaves the docs telling you to type a command that does not exist, and that fails with
    `command not found`, with no hint that the wrong one is the doc and not the machine.
    """
    declared = _CONSOLE_SCRIPT.search(_read(_ROOT / "pyproject.toml"))
    assert declared, "pyproject.toml declares no executable in [project.scripts]"

    wrong: dict[str, list[str]] = {}
    for source in _LAUNCH_SOURCES:
        for named in _LAUNCH.findall(_read(_ROOT / source)):
            if named != declared.group(1):
                wrong.setdefault(source, []).append(named)

    assert not wrong, (
        f"these docs launch the program with a name [project.scripts] does not declare ({declared.group(1)}):\n"
        + "\n".join(f"  {source}: {', '.join(found)}" for source, found in sorted(wrong.items()))
    )


@pytest.mark.integration
def test_no_doc_still_tells_you_to_put_the_import_path_by_hand() -> None:
    """The old form is no longer needed, and leaving it written is worse than documenting nothing.

    Whoever copies it gets no error: they get an invocation that works by another road and the belief
    that the package is still not installed, which is exactly what this slice has just changed.
    """
    stale = {
        source: found
        for source in _LAUNCH_SOURCES
        if (found := [line.strip() for line in _STALE_LAUNCH.findall(_read(_ROOT / source))])
    }

    assert not stale, "these docs still tell you to put the import path by hand:\n" + "\n".join(
        f"  {source}: {', '.join(found)}" for source, found in sorted(stale.items())
    )


def test_the_exit_codes_the_readme_documents_are_the_ones_the_program_can_return() -> None:
    """`docs/conventions/infrastructure.md` says the exit codes are a contract and are documented.

    They are the whole output of a run for whoever scripts it: `1` is a verdict and `2` is the absence
    of one, and a caller that cannot tell them apart retries a veto or merges an unjudged slice. The
    convention was being broken by its own slice -- the enum existed, the tests pinned it, and there was
    nowhere to read it. A new member added without documenting it is the failure this catches.
    """
    documented = {int(code) for code in re.findall(r"^\| `(\d+)` \|", _read(_README), re.MULTILINE)}

    assert documented == {int(code) for code in ExitCode}, (
        f"README.md and ExitCode disagree: only in the README {sorted(documented - {int(c) for c in ExitCode})}, "
        f"only in the enum {sorted({int(c) for c in ExitCode} - documented)}"
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
