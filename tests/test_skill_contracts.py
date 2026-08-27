"""Contract tests between the program and the documentation it is read against.

`make check` covers the Python scripts, but the skills and the judge's rubric are markdown, and
every contract they share with the program that parses or builds them -- or with each other -- is
currently stated twice. Two copies drift the moment only one is edited, and nothing fails when
they do: the runner keeps emitting a marker the parser no longer knows, or one half of a
deliberately duplicated policy gets "fixed" on its own.

Each test here extracts a vocabulary from one surface and compares it against the other, rather
than asserting that a given sentence is present. Rewording that keeps both sides in step passes;
changing one side alone fails. That is the only drift these tests exist to catch.

Two other kinds of contract used to live in this file and do not any more:
`test_domain_vocabulary_contracts.py` holds the two that compare two vocabularies of the program's
own domain with no document in between, and `test_pipeline_invariants.py` holds the six that scan
the tree instead of comparing two copies of the same prose.
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

_UNDERSTANDING_ANCHORS = ("el fichero existe no cumple", "declara que esa vara se aplico", "no un informe")
"""Same kind of claim as `_CONFIRMATION_ANCHORS`, for the pause that publishes what got understood.

None of the three has a second surface to compare against: step `1b` confirms pointers -- a path, an
issue number -- never whether the behaviour behind them was understood, and the feature's
acceptance criteria are confirmed here and never written to the parent issue. So this is a claim
about the prose, and rewording any of them moves its anchor with it.

The third one is what keeps the other two from decaying into a gate nobody reads. `check-alignment`
asks for the understanding to be succinct so it stays scannable, and this repo has already paid for
what happens otherwise: an understanding whose whole body said `test` went through the downstream
gate. An unscannable pause gets waved through, and a pause that gets waved through catches nothing.
"""

_EXISTING_PIECE_ANCHORS = ("que hace hoy esa pieza", "una ruta que existe deja de cumplir")
"""Anchors for the rule that a `- pieza:` line names behaviour, not just that a path exists.

Step `1b` already confirms the pointer -- the path itself -- so a `- pieza:` line that only restates
it is a file census a spec could pass without anybody reading what the code does. Same kind of claim
as `_CONFIRMATION_ANCHORS`: no second surface parses this prose, so the anchors travel with the
sentence in the hard rules and in the matching `validate` checklist item.
"""

_EXISTING_PIECE_LOCATION_ANCHOR = "reportandola como `issue padre`"
"""Where the `validate` checklist owes reporting the `- pieza:` deviation it just learned to catch.

`_VALIDATE_ANCHORS` already contains the literal string `issue padre`, but it is satisfied by an
unrelated checklist item, so deleting this phrase alone leaves that broader test green. This anchor
is scoped to the sentence under test, not the whole `validate` section.
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

_SUBISSUE_LINES = frozenset({"REPO", "INTENCION", "ACEPTACION", "SENAL", "EXCLUYE", "SUSTITUYE"})
"""The six labelled lines a subissue body carries, written down instead of derived from the example.

`REPO:`, `SENAL:`, `EXCLUYE:` and `SUSTITUYE:` all have a consumer in the program now, read by
`SubissueBody` and measured by the tests above and below. `INTENCION:` and `ACEPTACION:` travel as prose
to the implementer and to `deploy-watch`, with no second surface to compare the set against, and
deriving it from the very example under test approves whatever the example happens to say: drop
`SENAL:` from the three regions at once and all three sets still match. So the set is an external claim
about the prose, with its reason next to it, like `_CONFIRMATION_ANCHORS`.
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

    The six labelled lines are asserted, not just `REPO:`, because all six now have a consumer: the
    intention, the criteria, the signal, what is excluded and what is replaced travel into the prompts
    of the implementer and of the judge. Parsing them is fail-soft by design -- a line the parser does
    not recognise is not an error, it is an empty field -- so a rename on one side alone would leave both
    agents working with an empty yardstick and nothing at all would break. `_SUBISSUE_LINES` already
    claims the example writes the six; this is what checks the program reads the six.
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
    assert children[0].excludes, "the documented subissue carries no `EXCLUYE:` the program can read"
    assert children[0].replaces, "the documented subissue carries no `SUSTITUYE:` the program can read"
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
        f"{sorted(_SUBISSUE_LINES)}: the intention, the criteria, the signal, what is excluded and the "
        f"target repo"
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
    "la etiqueta `origen:<clave>`",
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


_REPLACES_VALIDATE_ANCHORS = (
    "Ninguna slice sin `SUSTITUYE:`, y ninguna `SUSTITUYE: si` sin las dos mitades",
    "es la misma desviacion: sin el mecanismo de vuelta atras",
    "tiene que ser la que corresponde al sujeto",
)
"""Anchors for the checklist item that catches a missing `SUSTITUYE:` and an incomplete `SUSTITUYE: si`.

Same kind of claim as `_USER_STORY_VALIDATE_ANCHORS`: the two halves of this bullet -- the line missing
entirely, and a `si` that names only one of the two things it owes -- are both prose with no second
surface to compare against, so this pins the sentence that reports each one instead of a vocabulary.
"""


def test_validate_reports_a_missing_replaces_line_and_an_incomplete_si_declaration() -> None:
    """`validate` has to catch both a subissue without `SUSTITUYE:` and one whose `si` skips a half.

    A `SUSTITUYE: si` that names what it replaces but not how to roll it back leaves the judge's rollout
    item with nothing to demand from the diff, which is the exact failure mode the line exists to close.
    """
    prose = " ".join(_spec_prose(_VALIDATE).split())

    missing = [anchor for anchor in _REPLACES_VALIDATE_ANCHORS if anchor not in prose]
    assert not missing, (
        f"the `validate` mode of {_rel(_SPEC)} no longer states {missing}: a subissue missing "
        f"`SUSTITUYE:` or declaring `SUSTITUYE: si` without both halves needs to be caught and reported"
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


def test_the_step_between_the_repo_search_and_the_slicing_publishes_what_it_understood_and_waits() -> None:
    """Neither half of this pause has anywhere else to be measured against.

    Step `1b` only confirms pointers -- a path, an issue number -- never whether the behaviour behind
    them was understood, and the feature's acceptance criteria used to appear only inside the
    subissues the slicing step writes, with nobody having seen the whole list first. This step is the
    one place both get shown and confirmed before any slice is cut.
    """
    steps = re.split(r"^(?=\d+[a-z]?\.\s)", _spec_prose(_AUTHORING_STEPS), flags=re.MULTILINE)
    pause = [step for step in steps if step.strip().startswith("1c.")]
    assert len(pause) == 1, f"expected exactly one step of {_rel(_SPEC)} numbered `1c.`, found {len(pause)}"

    step = pause[0]
    missing = [anchor for anchor in _UNDERSTANDING_ANCHORS if anchor not in step]
    assert not missing, (
        f"step `1c.` of {_rel(_SPEC)} no longer states {missing}: nothing else in the tree confirms that "
        f"the code was understood, proposes the feature's acceptance criteria before cutting, or keeps "
        f"the pause short enough to be read instead of waved through"
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


_PIECE_LINE = re.compile(r"^- pieza: \S+ - (.+?)(?=\n- |\Z)", re.MULTILINE | re.DOTALL)


def test_the_existing_piece_lines_name_behaviour_and_the_documented_example_shows_it() -> None:
    """`- pieza:` used to pass by naming a path that exists; now it owes what that path does today.

    The hard rules state the bar, `validate` catches a spec written under the old one, and the
    parent's example is what a model copies verbatim -- so a rule that tightened without the example
    following would have the skill teaching the very shape it now rejects. This is the comparison
    `docs/conventions/testing.md` asks for between two copies of the same contract: reword one side
    and the other stays behind.
    """
    hard_rules = _spec_prose(_HARD_RULES)
    missing_in_rules = [anchor for anchor in _EXISTING_PIECE_ANCHORS if anchor not in hard_rules]
    assert not missing_in_rules, (
        f"the hard rules of {_rel(_SPEC)} no longer state {missing_in_rules}: a `- pieza:` line that "
        f"only names a path that exists has to stop being enough"
    )

    validate_prose = _spec_prose(_VALIDATE)
    missing_in_validate = [anchor for anchor in _EXISTING_PIECE_ANCHORS if anchor not in validate_prose]
    assert not missing_in_validate, (
        f"the `validate` checklist of {_rel(_SPEC)} no longer states {missing_in_validate}: it has to "
        f"catch a `- pieza:` line that only names an existing path"
    )
    assert _EXISTING_PIECE_LOCATION_ANCHOR in validate_prose, (
        f"the `validate` checklist of {_rel(_SPEC)} no longer states {_EXISTING_PIECE_LOCATION_ANCHOR!r}: "
        f"a deviation reported without its location is one the person has to go and find"
    )

    example = _spec_example(_PARENT_EXAMPLE)
    pieces = _PIECE_LINE.findall(example)
    assert pieces, f"the documented parent under {_PARENT_EXAMPLE} carries no `- pieza:` line to check"
    for tail in pieces:
        assert "existe" not in tail, (
            f"the documented `- pieza:` line {tail!r} still describes the piece as existing, which is "
            f"exactly what the tightened rule rejects"
        )


_GRACE_WINDOW_IS_WRITTEN_IN = (
    _ROOT / "docs" / "design-notes.md",
    _ROOT / "README.md",
)


def _grace_window(text: str) -> tuple[int, int]:
    """The two numbers of the grace window as some surface writes them: ticks and seconds."""
    ticks = re.search(r"(\d+)\s+ticks\s+indeterminados", text)
    assert ticks, "the grace window is stated without how many ticks it takes"
    seconds = re.search(r"(\d+)\s+s\s+o\s+m[aá]s\s+entre\s+tick\s+y\s+tick", text)
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


def test_the_rubric_reads_excludes_as_a_prohibition_and_never_as_a_permission() -> None:
    """`EXCLUYE` is what the spec wrote down as deliberately out of this slice's scope, and the

    implementer's brief tells it not to build what that line names. So item 5 has to fail a diff that
    builds it anyway: read as a permission, the line would have the judge wave through exactly what the
    other half of the pipeline forbids, and the two prompts would contradict each other on the same
    input.
    """
    rubric = _program_rubric()
    assert "Contrasta esto contra el `EXCLUYE`" in rubric, (
        "the program's rubric no longer tells the judge to contrast item 5's speculative-behaviour check "
        "against `EXCLUYE`, so what the spec forbade would be judged as if nobody had ever written it down"
    )
    assert "el diff construye lo que el `EXCLUYE` prohibia" in rubric, (
        "the program's rubric no longer fails a diff that builds what `EXCLUYE` declared out of scope, so "
        "the line stopped being a prohibition for the judge while it still is one for the implementer"
    )
    assert "`EXCLUYE` tampoco cubra" not in rubric, (
        "the program's rubric exempts from item 5's FAIL condition what `EXCLUYE` names, which reads the "
        "line as a list of permissions: it is a list of prohibitions"
    )


def test_the_rubric_lists_excludes_among_the_inputs_that_can_arrive_empty() -> None:
    """`EXCLUYE` travels the same fail-soft path as `SENAL`: a slice that never declares one parses to

    an empty field, not an error. Without the rubric saying so, the judge reading an empty `EXCLUYE`
    line has no way to tell "nothing was declared out of scope" from "the input never reached me", and
    the two need different verdicts (see the paragraph on reporting missing inputs).
    """
    rubric = _program_rubric()
    assert "Seis de esos campos pueden llegarte vacios" in rubric, (
        "the program's rubric still says five fields can arrive empty, but `SUSTITUYE` joined `EXCLUYE` "
        "and `SENAL` on the same fail-soft path and needs to be counted among them"
    )
    assert "el `EXCLUYE`" in rubric, (
        "the program's rubric no longer names `EXCLUYE` among the inputs that can arrive empty"
    )
    assert "el `SUSTITUYE`" in rubric, (
        "the program's rubric no longer names `SUSTITUYE` among the inputs that can arrive empty"
    )


def test_the_rubric_demands_the_rollback_mechanism_when_the_slice_declares_it_replaces_something() -> None:
    """`SUSTITUYE: si` names the mechanism; item 2 has to fail a diff that does not bring it back.

    Without this, a slice that declares it replaces live behaviour could still land as an in-place swap
    with no way back except a redeploy -- exactly the anti-pattern `slicing.md` names, now with a
    declared line the judge has no excuse to skip.
    """
    rubric = " ".join(_program_rubric().split())
    assert "SUSTITUYE: si" in rubric, (
        "the program's rubric no longer contrasts item 2 against a `SUSTITUYE: si` declaration"
    )
    assert "el mecanismo de vuelta atras que la linea nombra" in rubric, (
        "the program's rubric no longer demands the diff bring back the rollback mechanism the "
        "`SUSTITUYE: si` line names"
    )
    assert "Si no esta, es **FAIL (severity high)**, citando la linea de `SUSTITUYE`" in rubric, (
        "the program's rubric demands the rollback mechanism but no longer blocks with severity high "
        "when it is missing from the diff"
    )


def test_the_rubric_treats_a_declared_no_replacement_as_refutable_against_the_diff() -> None:
    """`SUSTITUYE: no` is a claim about the diff, not an exemption from item 2.

    A slice that declares it replaces nothing but whose diff changes behaviour that already existed in
    production is exactly the silent in-place swap the line exists to catch; treating the declaration as
    true by default would make it decoration.
    """
    rubric = " ".join(_program_rubric().split())
    assert "SUSTITUYE: no" in rubric, "the program's rubric no longer contrasts item 2 against `SUSTITUYE: no`"
    assert "el diff cambia comportamiento que ya existia" in rubric, (
        "the program's rubric no longer fails a `SUSTITUYE: no` slice whose diff changes behaviour that "
        "already existed in production"
    )
    assert (
        "en produccion pese a la declaracion, es **FAIL (severity high)**, citando la linea y el cambio "
        "que la contradice" in rubric
    ), (
        "the program's rubric treats a contradicted `SUSTITUYE: no` as refutable but no longer blocks "
        "with severity high when the diff proves it wrong"
    )


def test_the_rubric_judges_rollout_as_before_when_replaces_is_empty_and_not_as_missing_data() -> None:
    """An empty `SUSTITUYE` is every spec written before this line existed, not a missing input.

    Same shape as the `EXCLUYE` paragraph right above: the item still has its general trigger to fall
    back on, so a judge reading an empty line has no reason to return "sin veredicto por falta de dato"
    on the item that is the whole reason this rubric calls out the pattern as a recurrent failure.
    """
    rubric = " ".join(_program_rubric().split())
    assert "Si viene vacio, juzga el patron de rollout" in rubric, (
        "the program's rubric no longer tells the judge how to treat an empty `SUSTITUYE`: derive the "
        "rollout item from the general trigger instead of reporting it as missing data"
    )


def test_the_rubric_reads_an_empty_list_of_prior_findings_as_the_first_round_not_missing_data() -> None:
    """An empty list here means round one, the opposite of what emptiness means for the six fields above.

    Without this the judge has no way to tell "nothing survived from last time" from "this input never
    reached me", and the paragraph right above already claims the second reading for six other fields:
    the two would collide on the same rubric if this one were not called out apart from them.
    """
    rubric = " ".join(_program_rubric().split())
    assert "La lista de hallazgos de la ronda anterior vacia no es lo mismo que un insumo que no llego." in rubric, (
        "the program's rubric no longer distinguishes an empty prior-findings list from a missing input"
    )
    assert "esta es la primera verificacion de la slice" in rubric, (
        "the program's rubric no longer tells the judge that an empty prior-findings list means this "
        "is the first verification of the slice"
    )


def test_the_rubric_demands_a_verdict_on_every_prior_finding_with_a_reason_to_retire_one() -> None:
    """Every previous finding needs a fate, and retiring one without saying why is the silent U-turn

    this whole slice exists to close: 12 of 32 followable highs evaporated across a round with nobody
    saying why, and each one cost a round of implementation plus one of verification.
    """
    rubric = " ".join(_program_rubric().split())
    assert "pronunciate sobre **cada uno**" in rubric, (
        "the program's rubric no longer demands a verdict on every finding of the previous round"
    )
    for fate in ("**corregido**", "**sigue**", "**retirado**"):
        assert fate in rubric, f"the program's rubric no longer offers {fate} as a fate for a prior finding"
    assert "el `detail` del veredicto tiene que decir por que" in rubric, (
        "the program's rubric no longer demands a written reason in `detail` when a prior finding is retired"
    )


def test_the_rubric_treats_prior_findings_as_precedent_and_not_as_a_yardstick_to_drag_along() -> None:
    """Keeping a finding alive means re-citing it against the current diff, not repeating last round's

    citation as if nothing had moved: what changed between rounds may have shifted the line or fixed
    the file halfway, and dragging the old citation forward would report something no longer true.
    """
    rubric = " ".join(_program_rubric().split())
    assert "Son antecedente, no vara." in rubric, (
        "the program's rubric no longer declares prior findings a precedent instead of a yardstick"
    )
    assert "vuelve a citarlo contra el diff de esta ronda" in rubric, (
        "the program's rubric no longer requires re-citing a finding that still stands against the "
        "current diff instead of dragging the old citation forward"
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
