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
import importlib
import json
import re
import subprocess
import tomllib
from pathlib import Path

import pytest

import controles
import issue_body
import metrics
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity
from slice_runner.domain.step import Step
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.infrastructure.local_skill_library import LocalSkillLibrary
from slice_runner.infrastructure.slice_verifier_judge import SliceVerifierJudge
from slice_runner.infrastructure.verdict_payload import FindingPayload

_ROOT = Path(__file__).resolve().parents[1]
_RUNNER = _ROOT / "skills" / "slice-runner" / "SKILL.md"
_CONTROLES = _ROOT / "skills" / "slice-runner" / "scripts" / "controles.py"
_DEPLOY_WATCH = _ROOT / "skills" / "deploy-watch" / "SKILL.md"
_VERIFIER = _ROOT / "agents" / "slice-verifier.md"


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
    """Paths git tracks, so the check measures the repo as published, not the local mess."""
    out = subprocess.run(
        ["git", "-C", str(_ROOT), "ls-files", "-z", "--", *patterns],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted(p for p in out.split("\0") if p)


def test_blocked_reasons_written_by_the_runner_are_the_ones_the_parser_knows() -> None:
    """`bloqueada: X` markers in the runner must be exactly `issue_body.MotivoBloqueada`.

    The runner writes these markers into the issue body; `issue_body` is what reads them back.
    A reason documented but unknown to the parser makes the slice line unreadable downstream;
    a reason known to the parser but never written is dead vocabulary. The legacy alias
    (`puertas`) is deliberately excluded: the parser still accepts it for issues opened before
    the rename, but the runner must never emit it again.
    """
    written = set(re.findall(r"`bloqueada: ([a-z0-9-]+)`", _read(_RUNNER)))

    assert written == set(issue_body.MotivoBloqueada), (
        f"{_rel(_RUNNER)} and issue_body.MotivoBloqueada disagree on the blocked reasons: "
        f"only in the skill {sorted(written - set(issue_body.MotivoBloqueada))}, "
        f"only in the parser {sorted(set(issue_body.MotivoBloqueada) - written)}"
    )


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
    translator knows about. `PENDING` is written by a person when they create a subissue
    (`CLAUDE.md`'s slice). `AWAITING_ALIGNMENT` is written by `RunRepository.pause_for_alignment`
    before any `Run` exists, so there is no closure yet for the translator to project it from.
    Every other member has to come out of some `(RunState, Step)` pair the translator projects, or
    it is dead vocabulary nobody ever writes.
    """
    manual_source = {IssueLabel.PENDING, IssueLabel.AWAITING_ALIGNMENT}
    produced = {IssueLabel.of(state=state, step=step) for state in RunState for step in Step} - {None}

    assert set(IssueLabel) - produced == manual_source


def test_ci_states_branched_on_by_step_9_are_the_ones_the_script_emits() -> None:
    """Step 9 branches once per `ci-status` state; the script is what produces them.

    A state the skill never branches on is a run that falls through with no rule; a state
    the skill invents is a branch that never fires. Both were live risks the moment
    `ci-status` gained a fifth state that is neither green nor red.
    """
    step_9 = re.search(r"^### 9\..*?(?=^### )", _read(_RUNNER), re.MULTILINE | re.DOTALL)
    assert step_9, f"cannot find step 9 in {_rel(_RUNNER)}"

    branched: set[str] = set()
    for bullet in re.findall(r"^- \*\*(.+?)\*\*:", step_9.group(0), re.MULTILINE):
        branched |= set(re.findall(r"`([a-z-]+)`", bullet))

    assert branched == set(controles.EstadoCI), (
        f"{_rel(_RUNNER)} step 9 and controles.EstadoCI disagree on the CI states: "
        f"only in the skill {sorted(branched - set(controles.EstadoCI))}, "
        f"only in the script {sorted(set(controles.EstadoCI) - branched)}"
    )


_GRACE_WINDOW_IS_WRITTEN_IN = (
    _RUNNER,
    _CONTROLES,
    _ROOT / "skills" / "slice-runner" / "references" / "por-que.md",
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

    The number lived in two places on purpose -- step 9 of the runner, which counts the ticks, and
    the docstring of `ci-status`, which explains why its exit code 4 is one of them -- but it was
    written in five, and the state machine makes it six, because it is the machine that now decides
    when the window is spent. Copies of a policy number with no test is how a run closes
    `bloqueada: ci-indeterminada` after one tick while the prose still promises three. Every surface
    that states the number is in here: a copy left out is measured by nothing, which is the state
    this test exists to end.
    """
    budgets = Budgets()
    written = {_rel(path): _grace_window(_read(path)) for path in _GRACE_WINDOW_IS_WRITTEN_IN}

    assert set(written.values()) == {(budgets.indeterminate_ticks, budgets.seconds_between_ticks)}, (
        f"the grace window of {type(budgets).__name__} is "
        f"{(budgets.indeterminate_ticks, budgets.seconds_between_ticks)} and the prose writes {written}"
    )


def test_verdicts_the_runner_records_are_the_ones_the_metrics_cli_accepts() -> None:
    """The `--veredicto <...>` literal in the runner must match `metrics.Veredicto`.

    The runner spells the accepted values inline in the command it tells the agent to run.
    If they drift, the closing step of a slice fails on an argparse error at the exact moment
    the run is meant to be recorded -- the one place where a failure loses the data outright.
    """
    spelled = re.findall(r"--veredicto <([^>]+)>", _read(_RUNNER))
    assert len(spelled) == 1, (
        f"expected exactly one `--veredicto <...>` literal in {_rel(_RUNNER)}, found {len(spelled)}"
    )
    documented = set(spelled[0].split("|"))

    assert documented == set(metrics.Veredicto), (
        f"{_rel(_RUNNER)} and metrics.Veredicto disagree on the recordable verdicts: "
        f"only in the skill {sorted(documented - set(metrics.Veredicto))}, "
        f"only in the CLI {sorted(set(metrics.Veredicto) - documented)}"
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


def _sole_json_block(path: Path) -> object:
    return _sole_json_block_in(_read(path), where=_rel(path))


def _sole_json_block_in(markdown: str, *, where: str = "the program's rubric") -> object:
    blocks = re.findall(r"```json\n(.*?)```", markdown, re.DOTALL)
    assert len(blocks) == 1, f"expected exactly one ```json block in {where}, found {len(blocks)}"
    return json.loads(blocks[0])


def test_verifier_verdict_schema_is_identical_in_the_agent_and_in_the_runner() -> None:
    """The verdict JSON is stated in full in both the agent prompt and the runner.

    The agent's system prompt is what actually produces the object; the runner's copy is what
    the orchestrator is told to consume. There is no schema validation between them, so a field
    renamed on one side alone is read as absent on the other and silently ignored.
    """
    assert _json_shape(_sole_json_block(_VERIFIER)) == _json_shape(_sole_json_block(_RUNNER)), (
        f"the verdict JSON in {_rel(_VERIFIER)} and {_rel(_RUNNER)} no longer have the same "
        f"shape; both copies describe the same contract and must be updated together"
    )


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


def test_severity_levels_in_the_verdict_schema_are_the_ones_the_validator_accepts() -> None:
    """The rubric's severities and the validator's must be the same set.

    `verify-verdict` rejects a severity it does not know, so a level documented in the skill
    but absent from the script turns a legitimate verdict into a discarded invocation -- and
    the reverse silently widens what counts as a valid finding.
    """
    schema = _sole_json_block(_RUNNER)
    assert isinstance(schema, dict)
    hallazgos = schema["hallazgos"]
    assert isinstance(hallazgos, list)
    assert hallazgos
    primero = hallazgos[0]
    assert isinstance(primero, dict)
    documented = {s.strip() for s in str(primero["severidad"]).split("|")}

    assert documented == set(controles.Severidad), (
        f"the verdict schema in {_rel(_RUNNER)} and controles.Severidad disagree: "
        f"only in the skill {sorted(documented - set(controles.Severidad))}, "
        f"only in the validator {sorted(set(controles.Severidad) - documented)}"
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


_CRITERION_ANCHOR = "declarar la degradacion en el artefacto"
"""Short, stable phrase used only to locate the criterion.

The sentence it belongs to is extracted from the files rather than hardcoded here, so rewording
both copies in step still passes.
"""


def _degradation_criterion(path: Path) -> str:
    """The bold question that both skills use to decide between degrading and stopping."""
    questions: list[str] = [
        question for question in re.findall(r"\*\*(¿[^*]+?\?)\*\*", _read(path)) if _CRITERION_ANCHOR in question
    ]
    assert len(questions) == 1, (
        f"expected exactly one degradation criterion in {_rel(path)}, found {len(questions)}; "
        f"both skills must state it, because neither loads the other"
    )
    return questions[0]


def test_both_skills_state_the_same_degradation_criterion_word_for_word() -> None:
    """`slice-runner` and `deploy-watch` duplicate this criterion on purpose.

    The decision to duplicate accepted drift as its cost, in exchange for each skill being
    self-contained and versioned in this repo. This test pays that cost off: the two copies are
    compared against each other, so rewording them together is free and rewording one is not.
    """
    assert _degradation_criterion(_RUNNER) == _degradation_criterion(_DEPLOY_WATCH), (
        f"the degradation criterion has drifted between {_rel(_RUNNER)} and "
        f"{_rel(_DEPLOY_WATCH)}; it is duplicated deliberately and both copies must say the same"
    )


def test_each_skill_names_the_other_when_declaring_its_side_of_the_criterion() -> None:
    """The asymmetry (one stops, one degrades) only reads as coherent with the cross-citation.

    Same criterion, different artifact, opposite conclusions. Without each skill pointing at the
    other, a future reader sees two skills contradicting each other and harmonises them -- almost
    certainly towards degrading both, which is the side that destroys the guarantee.
    """
    assert "deploy-watch" in _read(_RUNNER), (
        f"{_rel(_RUNNER)} no longer cites deploy-watch; the asymmetry then reads as a bug"
    )
    assert "slice-runner" in _read(_DEPLOY_WATCH), (
        f"{_rel(_DEPLOY_WATCH)} no longer cites slice-runner; the asymmetry then reads as a bug"
    )


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

_LAUNCH = re.compile(r"[^\n`|]*python -m slice_runner")


@pytest.mark.integration
def test_every_documented_way_to_launch_the_program_carries_the_import_path() -> None:
    """`package = false` means the program is not installed, so `python -m` alone cannot find it.

    The command is written in three places on purpose -- the README (how you run it), `pyproject.toml`
    (why the path is needed) and `docs/conventions/architecture.md` (the table that tells the two kinds
    of Python code apart) -- and one of them said `uv run python -m slice_runner` with no `PYTHONPATH`.
    That does not fail with a hint: it fails with `No module named slice_runner`, and the reader has no
    reason to doubt the yardstick. This is the one contract where a copy that does not run is worse than
    no copy at all.
    """
    missing: dict[str, list[str]] = {}
    for source in ["README.md", "pyproject.toml", *_tracked("docs/conventions/*.md")]:
        for invocation in _LAUNCH.findall(_read(_ROOT / source)):
            if "PYTHONPATH=src" not in invocation:
                missing.setdefault(source, []).append(invocation.strip())

    assert not missing, "these documented invocations of the program cannot import it:\n" + "\n".join(
        f"  {source}: {', '.join(found)}" for source, found in sorted(missing.items())
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
