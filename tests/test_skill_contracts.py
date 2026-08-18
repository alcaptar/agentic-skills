"""Contract tests between the program and the documentation it is read against.

`make check` covers the Python scripts, but the skills and the judge's rubric are markdown, and
every contract they share with the program that parses or builds them -- or with each other -- is
currently stated twice. Two copies drift the moment only one is edited, and nothing fails when
they do: the runner keeps emitting a marker the parser no longer knows, or one half of a
deliberately duplicated policy gets "fixed" on its own.

Each test here extracts a vocabulary from one surface and compares it against the other, rather
than asserting that a given sentence is present. Rewording that keeps both sides in step passes;
changing one side alone fails. That is the only drift these tests exist to catch.

Three other kinds of contract used to live in this file and do not any more:
`test_domain_vocabulary_contracts.py` holds the two that compare two vocabularies of the program's
own domain with no document in between, `test_metrics_bridge_contract.py` holds the two that are
the last bridge with `metrics.py`, and `test_pipeline_invariants.py` holds the six that scan the
tree instead of comparing two copies of the same prose.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import pytest
from conftest import _ROOT, _read, _rel, _tracked

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.severity import Severity
from slice_runner.domain.state_machine import StateMachine
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.infrastructure.gh_run_repository import GhRunRepository
from slice_runner.infrastructure.local_skill_library import LocalSkillLibrary
from slice_runner.infrastructure.parent_body import ParentBody
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.infrastructure.slice_verifier_judge import SliceVerifierJudge
from slice_runner.infrastructure.subissue_body import SubissueBody
from slice_runner.infrastructure.transition_payload import TransitionPayload
from slice_runner.infrastructure.transition_request_payload import TransitionRequestPayload
from slice_runner.infrastructure.verdict_payload import FindingPayload
from slice_runner.tests.doubles import GhCallDoubles, ScriptedProcess

if TYPE_CHECKING:
    from pathlib import Path

_SPEC = _ROOT / "skills" / "slice-spec" / "SKILL.md"


_PROGRAM_JUDGE = SliceVerifierJudge.adversarial()
"""The judge the PROGRAM builds, which owns its rubric, its tools and what it may read.

The old flow's `agents/slice-verifier.md` had no consumer left once the skill that invoked it was
retired, and is gone; the program owns the judge, so every contract about what it tells the judge is
measured against this.
"""


def _program_rubric() -> str:
    return _PROGRAM_JUDGE.rubric


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

    children = GhRunRepository(call=GhCallDoubles.wired(process)).read_children(
        repo="alcaptar/agentic-skills", parent=43, expected=1
    )

    assert _KEBAB_TITLE.match(title), f"the documented title {title!r} does not carry `slice-NN (name-kebab):`"
    assert children[0].slice_id.canonical == title.split(" ", 1)[0]
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


_USER_STORY_KEY_LINE = re.compile(r"## Historia de usuario\s*\n\s*([A-Z][A-Z0-9]*-\d+)")
_USER_STORY_TITLE = re.compile(r"`([A-Z][A-Z0-9]*-\d+ slice-\d+ \([^`)]+\): [^`]+)`")


def test_the_user_story_key_the_parent_documents_is_the_one_the_program_reads_from_the_subissue_title() -> None:
    """The key the parent declares has to be the same one `GhRunRepository` parses out of the title.

    `SLICE_HEADING` already carries an optional `key` group that `read_children` composes into the
    canonical identifier, but nothing writes it yet: this is the contract between what `slice-spec`
    documents as the parent's declared key and what the program's own expression reads back out of the
    documented subissue title, parsed with that expression rather than restated by hand.
    """
    text = _read(_SPEC)
    key_match = _USER_STORY_KEY_LINE.search(text)
    assert key_match, f"{_rel(_SPEC)} does not document a `## Historia de usuario` example carrying a key"
    declared_key = key_match.group(1)

    title_match = _USER_STORY_TITLE.search(text)
    assert title_match, f"{_rel(_SPEC)} does not document a subissue title carrying a user story key"
    title = title_match.group(1)

    parsed = GhRunRepository.SLICE_HEADING.match(title)
    assert parsed, f"the documented keyed title {title!r} is not parseable by `GhRunRepository.SLICE_HEADING`"
    assert parsed.group("key") == declared_key, (
        f"the parent documents the key {declared_key!r} but the documented subissue title parses as "
        f"{parsed.group('key')!r}: the two halves of the contract disagree"
    )


_USER_STORY_VALIDATE_ANCHORS = (
    "declara `## Historia de usuario` pero alguna subissue no lleva la clave en el titulo",
    "no empieza por esa clave seguida de `slice-NN`",
    "reportala como `slice-NN (#numero)`, en el titulo",
    "la clave va delante del `slice-NN`",
)
"""Anchors for the checklist item that catches a parent/subissue mismatch on the user story key.

Same kind of claim as `_VALIDATE_ANCHORS`: there is no second surface to compare this rule against, since
the key travels only through the title and the parent's own section, so this pins the sentence that
reports the deviation with its rule and its location.

Each anchor is a phrase from the new bullet only, not a bare substring: `validate`'s intro paragraph
already contains `slice-NN (#numero)` and `en el titulo` on their own (for the location of any
subissue deviation), so anchoring on those alone would stay green even if the bullet itself were
deleted. Anchoring on the longer phrases pins the bullet, not the paragraph that precedes it.
"""


_PARENT_USER_STORY_ANCHORS = (
    "pero su propio titulo no abre con la clave, o no lleva",
    "la etiqueta `historia:<clave>`",
    "reportalo como `issue padre`, diciendo cual de las dos",
)
"""Anchors for the checklist item that catches a parent not carrying its own user story key.

The key reaches the parent by two surfaces the program never reads -- its title and its label -- so
neither can be compared against anything the way `SLICE_HEADING` compares the documented subissue
title. Both exist for the same job: finding the whole feature in a listing without opening it, which
is also why losing one silently is easy. This pins the sentence that reports the deviation.
"""


def test_validate_reports_a_parent_that_does_not_carry_its_own_user_story_key() -> None:
    """`validate` has to catch a parent whose title or label drops the key its body declares.

    Same shape as the checklist anchors above: prose with no second surface, so the test pins the
    sentence instead of comparing two copies of a vocabulary.
    """
    prose = " ".join(_spec_prose(_VALIDATE).split())

    missing = [anchor for anchor in _PARENT_USER_STORY_ANCHORS if anchor not in prose]
    assert not missing, (
        f"the `validate` mode of {_rel(_SPEC)} no longer states {missing}: a parent that declares a "
        f"user story has to carry it in its own title and label, or the deviation goes unreported"
    )


def test_validate_reports_the_missing_user_story_key_with_its_rule_and_location() -> None:
    """`validate` has to catch a parent declaring a user story whose subissues do not carry it.

    Same shape as `test_the_validate_mode_reports_every_deviation_with_its_rule_and_where_it_lives`: the
    checklist item is prose with no second surface, so this pins the sentence rather than a vocabulary.
    """
    prose = " ".join(_spec_prose(_VALIDATE).split())

    missing = [anchor for anchor in _USER_STORY_VALIDATE_ANCHORS if anchor not in prose]
    assert not missing, (
        f"the `validate` mode of {_rel(_SPEC)} no longer states {missing}: a parent declaring a user "
        f"story whose subissue titles do not carry it needs to be caught and reported with its location"
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


_GRACE_WINDOW_IS_WRITTEN_IN = (
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


_EXPLAIN_EXAMPLE = re.compile(
    r"```bash\n(echo '.*?' \\\n\s*\| uv run [\w.-]+ explain\n)```\n\n```json\n(.*?)```", re.DOTALL
)
_EXPLAIN_REQUEST = re.compile(r"echo '(.+?)' \\")


def test_the_explain_example_the_readme_shows_is_the_transition_the_program_actually_returns() -> None:
    """`docs/conventions/infrastructure.md` says a contract written more than once needs a test.

    The request and the response of this example are typed by hand in the README, and nothing ran
    them through `StateMachine` until now: the response drifted the moment `Run` grew
    `control_rounds_logged` and the README kept the shape it had before that field existed.
    """
    example = _EXPLAIN_EXAMPLE.search(_read(_README))
    assert example, "README.md no longer shows the paired bash/json example of `explain`"
    request = _EXPLAIN_REQUEST.search(example.group(1))
    assert request, "the bash block of the `explain` example carries no `echo` request to replay"

    asked = TransitionRequestPayload.read(request.group(1))
    transition = StateMachine(budgets=Budgets()).after(asked.run.to_domain(), asked.outcome)

    assert TransitionPayload.from_domain(transition).to_contract() == json.loads(example.group(2)), (
        "the README's `explain` example no longer matches what the program returns for that same request"
    )


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
    would have no way to know which half is true. The old flow enforced the same thing structurally,
    through the `tools:` header of a now-retired `agents/slice-verifier.md`; the program has no header,
    so this is where it gets enforced.
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
    findings = schema["findings"]
    assert isinstance(findings, list)
    assert findings
    first = findings[0]
    assert isinstance(first, dict)
    return first


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

    assert {v.strip() for v in str(schema["ruling"]).split("|")} == set(Ruling)
    assert {s.strip() for s in str(_documented_finding()["severity"]).split("|")} == set(Severity)


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


def test_every_slice_title_slice_spec_documents_yields_a_name_git_accepts_as_a_branch() -> None:
    """The titles the skill shows are what a model imitates, so they have to survive `git switch -c`.

    `slice-spec` used to document an optional conventional-commit type inside the parentheses --
    `slice-03 (refactor: extraer-repo)` -- and the program consumed it nowhere: `GhRunRepository` takes
    the whole parentheses as the name, so the branch came out as `slice/03-refactor: extraer-repo` and
    git refused it. The run died on 2026-08-11 having already marked the subissue in progress, published
    the understanding and paid for the call, which is the worst moment to find out.

    Parsing the documented titles with the program's own expression is what keeps the two sides honest:
    a title the skill teaches and the program cannot turn into a branch fails here instead of mid-run.

    Covers both documented title shapes: the plain `slice-NN (name): title` and the one prefixed with a
    user story key, `AS-255 slice-NN (name): title`. Counting titles would not tell them apart -- the
    skill documents several plain ones, so any count stays green after the keyed example disappears --
    so the keyed shape is asserted by the `key` group the program itself parses out.
    """
    titles = re.findall(r"`((?:[A-Z][A-Z0-9]*-\d+ )?slice-\d+ \([^)]+\)[^`]*)`", _read(_SPEC))

    assert titles, "slice-spec documents no slice title, so this contract has nothing to measure"

    keyed = []
    for title in titles:
        parsed = GhRunRepository.SLICE_HEADING.match(title)
        assert parsed, f"the program cannot read the title slice-spec documents: {title}"
        name = parsed["name"]
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), (
            f"the title `{title}` yields the name `{name}`, which git will not take as a branch"
        )
        if parsed["key"]:
            keyed.append(title)

    assert keyed, (
        "slice-spec documents no title carrying a user story key, so the shape this guard was widened "
        "for is going unmeasured while the rest of the titles keep it green"
    )
