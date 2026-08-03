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
import dataclasses
import importlib
import json
import re
import subprocess
from pathlib import Path

import controles
import issue_body
import metrics
from slice_runner.domain import veredicto
from slice_runner.infrastructure import verificador

_ROOT = Path(__file__).resolve().parents[1]
_RUNNER = _ROOT / "skills" / "slice-runner" / "SKILL.md"
_DEPLOY_WATCH = _ROOT / "skills" / "deploy-watch" / "SKILL.md"
_VERIFIER = _ROOT / "agents" / "slice-verifier.md"


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
    blocks = re.findall(r"```json\n(.*?)```", _read(path), re.DOTALL)
    assert len(blocks) == 1, f"expected exactly one ```json block in {_rel(path)}, found {len(blocks)}"
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


def test_tools_the_program_grants_the_judge_are_the_ones_his_prompt_declares() -> None:
    """The agent header lists the judge's tools; `--tools` in the argv is what grants them.

    The header is stripped before the prompt travels, so a tool listed there and absent from the
    argv is simply not granted -- while the rubric that does travel keeps ordering the judge to use
    it (two of its nine items load a skill). That is a rubric with items the judge cannot execute,
    and neither the argv nor the prompt says so: the empty yardstick the rubric itself names as the
    root cause of silent deviations. The reverse -- granting what the prompt never mentions -- is a
    capability nobody wrote down.
    """
    header = re.search(r"\A---\n(.*?)\n---\n", _read(_VERIFIER), re.DOTALL)
    assert header, f"cannot find the YAML header in {_rel(_VERIFIER)}"
    listed = re.findall(r"^tools:\s*(.+)$", header.group(1), re.MULTILINE)
    assert len(listed) == 1, f"expected exactly one `tools:` line in the header of {_rel(_VERIFIER)}"
    declared = {tool.strip() for tool in listed[0].split(",")}

    argv = verificador.argv_del_verificador()
    granted = set(argv[argv.index("--tools") + 1].split(","))

    assert declared == granted, (
        f"{_rel(_VERIFIER)} and the argv of slice_runner's verifier disagree on the judge's tools: "
        f"only in the prompt {sorted(declared - granted)}, only in the argv {sorted(granted - declared)}"
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
    schema = _sole_json_block(_VERIFIER)
    assert isinstance(schema, dict)
    hallazgos = schema["hallazgos"]
    assert isinstance(hallazgos, list)
    assert hallazgos
    primero = hallazgos[0]
    assert isinstance(primero, dict)
    return primero


def test_the_finding_fields_in_the_rubric_are_the_ones_the_program_models() -> None:
    """The rubric states the finding's fields; `Hallazgo` is what the program converts them into.

    A field documented but not modelled is dropped on the way in -- silently, because the JSON
    schema the program sends is built from `Hallazgo` too, so the judge is never even asked for
    it. The reverse makes the program demand a field the rubric never told the judge to emit.
    """
    documented = set(_documented_finding())

    modelled = {f.name for f in dataclasses.fields(veredicto.Hallazgo)}
    assert documented == modelled, (
        f"the finding in {_rel(_VERIFIER)} and slice_runner's `Hallazgo` disagree: "
        f"only in the rubric {sorted(documented - modelled)}, only in the program {sorted(modelled - documented)}"
    )


def test_the_verdicts_and_severities_in_the_rubric_are_the_ones_the_program_accepts() -> None:
    """Same drift, on the two closed vocabularies.

    These reach the judge as `enum` values in `--json-schema`, so a level in the rubric that the
    program does not know is one the judge is forbidden from emitting -- and one the program knows
    but the rubric does not document is dead vocabulary nobody will ever produce.
    """
    schema = _sole_json_block(_VERIFIER)
    assert isinstance(schema, dict)

    assert {v.strip() for v in str(schema["veredicto"]).split("|")} == set(veredicto.Dictamen)
    assert {s.strip() for s in str(_documented_finding()["severidad"]).split("|")} == set(veredicto.Severidad)


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
