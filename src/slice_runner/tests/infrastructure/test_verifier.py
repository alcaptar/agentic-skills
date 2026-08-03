from __future__ import annotations

import json
from dataclasses import fields
from itertools import pairwise
from pathlib import Path

import pytest

from slice_runner.domain.diff import SliceDiff
from slice_runner.domain.verdict import (
    FINDING_CONTRACT_KEYS,
    Finding,
    InvalidVerdictError,
    Ruling,
    Severity,
)
from slice_runner.domain.verification import VerificationRequest
from slice_runner.infrastructure.process import Process, ProcessOutput
from slice_runner.infrastructure.verifier import ClaudeVerifier, verdict_schema, verifier_argv
from slice_runner.tests.infrastructure.support import RECORDED, RecordedProcess, payload, with_verdict

_A_HIGH_SEVERITY_FINDING: dict[str, object] = {
    "regla": "boundaries",
    "path": "src/x.py",
    "severidad": "alta",
    "evidencia": "requests in the domain",
    "detalle": "I/O goes behind a port",
}


_A_REQUEST = VerificationRequest(
    repo="/repos/project",
    instructions="You are the adversarial verifier.",
    diff=SliceDiff(slice_diff=Path("/bundle/slice.diff"), files=Path("/bundle/files.txt"), n_files=2),
)


def request_with_the_bundle_materialised(tmp_path: Path) -> VerificationRequest:
    return VerificationRequest(
        repo="/repos/project",
        instructions="You are the adversarial verifier.",
        diff=SliceDiff(slice_diff=tmp_path / "slice.diff", files=tmp_path / "files.txt", n_files=2),
    )


def test_the_tools_travel_in_a_single_comma_separated_argument() -> None:
    argv = verifier_argv(_A_REQUEST)

    assert argv[argv.index("--tools") + 1] == "Read,Grep,Glob,Skill"


def test_the_judge_gets_skill_because_two_items_of_his_rubric_load_one() -> None:
    argv = verifier_argv(_A_REQUEST)

    assert "Skill" in argv[argv.index("--tools") + 1].split(",")


def test_the_judge_gets_no_writing_or_running_tools_because_the_one_who_verifies_does_not_implement() -> None:
    argv = verifier_argv(_A_REQUEST)

    granted = argv[argv.index("--tools") + 1].split(",")
    assert set(granted).isdisjoint({"Bash", "Write", "Edit"})


def test_the_argv_bounds_the_mcp_servers_and_declares_the_verdict_schema() -> None:
    argv = verifier_argv(_A_REQUEST)

    assert "--strict-mcp-config" in argv
    schema = json.loads(argv[argv.index("--json-schema") + 1])
    assert schema["properties"]["veredicto"]["enum"] == ["PASA", "FALLA"]


def test_the_argv_asks_for_the_json_envelope_of_the_harness() -> None:
    argv = verifier_argv(_A_REQUEST)

    assert argv[argv.index("--output-format") + 1] == "json"


def _values_next_to(argv: list[str], flag: str) -> list[str]:
    return [argv[i + 1] for i, arg in enumerate(argv) if arg == flag and i + 1 < len(argv)]


def _values_that_hang_from_no_flag(argv: list[str]) -> list[str]:
    return [value for previous, value in pairwise(argv) if not value.startswith("-") and not previous.startswith("-")]


def test_the_argv_carries_no_positional_argument_because_every_value_hangs_from_its_own_flag() -> None:
    argv = verifier_argv(_A_REQUEST)

    assert argv[0] == "claude"
    assert _values_that_hang_from_no_flag(argv) == []


def test_the_judge_gets_tool_access_to_the_bundle_and_to_the_repo_he_has_to_read() -> None:
    argv = verifier_argv(_A_REQUEST)

    assert _values_next_to(argv, "--add-dir") == ["/bundle", "/repos/project"]


def test_each_directory_travels_with_its_own_flag_so_the_argv_does_not_depend_on_its_arity() -> None:
    argv = verifier_argv(_A_REQUEST)

    assert argv.count("--add-dir") == 2


@pytest.mark.parametrize("recorded", RECORDED)
def test_the_envelope_of_both_real_calls_is_read_whole_from_structured_output(recorded: str, tmp_path: Path) -> None:
    process = RecordedProcess(payload(recorded))

    verdict = ClaudeVerifier(process=process).verify(request_with_the_bundle_materialised(tmp_path))

    assert verdict.ruling is Ruling.FAIL
    assert len(verdict.findings) == 4


def test_the_finding_arrives_typed_down_to_its_severity(tmp_path: Path) -> None:
    process = RecordedProcess(payload("full-recipe"))

    first = ClaudeVerifier(process=process).verify(request_with_the_bundle_materialised(tmp_path)).findings[0]

    assert first.severity is Severity.HIGH
    assert first.rule == "convenciones"
    assert first.path == "mod.py"
    assert first.line == 11


def test_a_verdict_with_no_findings_passes(tmp_path: Path) -> None:
    process = RecordedProcess(with_verdict({"veredicto": "PASA", "hallazgos": []}))

    verdict = ClaudeVerifier(process=process).verify(request_with_the_bundle_materialised(tmp_path))

    assert verdict.ruling is Ruling.PASS
    assert verdict.findings == ()


def test_the_prompt_travels_on_standard_input_with_the_paths_of_the_bundle(tmp_path: Path) -> None:
    process = RecordedProcess(payload("full-recipe"))
    request = request_with_the_bundle_materialised(tmp_path)

    ClaudeVerifier(process=process).verify(request)

    assert request.instructions in process.stdin
    assert str(request.diff.slice_diff) in process.stdin
    assert str(request.diff.files) in process.stdin
    assert request.repo in process.stdin
    assert process.stdin not in process.argv


def test_a_pass_that_comes_with_a_high_severity_finding_is_rejected(tmp_path: Path) -> None:
    incoherent: dict[str, object] = {"veredicto": "PASA", "hallazgos": [_A_HIGH_SEVERITY_FINDING]}
    process = RecordedProcess(with_verdict(incoherent))

    with pytest.raises(InvalidVerdictError, match="PASA con 1 hallazgo"):
        ClaudeVerifier(process=process).verify(request_with_the_bundle_materialised(tmp_path))


def test_a_key_we_do_not_know_in_a_finding_is_rejected_instead_of_ignored(tmp_path: Path) -> None:
    with_an_extra_key: dict[str, object] = {
        "veredicto": "FALLA",
        "hallazgos": [_A_HIGH_SEVERITY_FINDING | {"campo_nuevo_del_juez": "invented"}],
    }
    process = RecordedProcess(with_verdict(with_an_extra_key))

    with pytest.raises(InvalidVerdictError, match="campo_nuevo_del_juez"):
        ClaudeVerifier(process=process).verify(request_with_the_bundle_materialised(tmp_path))


def test_a_key_we_do_not_know_in_the_envelope_is_rejected_instead_of_ignored(tmp_path: Path) -> None:
    process = RecordedProcess(dict(payload("full-recipe")) | {"campo_nuevo_del_harness": 1})

    with pytest.raises(InvalidVerdictError, match="campo_nuevo_del_harness"):
        ClaudeVerifier(process=process).verify(request_with_the_bundle_materialised(tmp_path))


def test_a_wrong_type_in_the_envelope_is_rejected(tmp_path: Path) -> None:
    process = RecordedProcess(dict(payload("full-recipe")) | {"is_error": "no"})

    with pytest.raises(InvalidVerdictError, match="`is_error` has to be true or false"):
        ClaudeVerifier(process=process).verify(request_with_the_bundle_materialised(tmp_path))


def test_an_envelope_without_structured_output_is_rejected_instead_of_falling_back_to_result(tmp_path: Path) -> None:
    without_structure = {k: v for k, v in payload("full-recipe").items() if k != "structured_output"}
    process = RecordedProcess(without_structure)

    with pytest.raises(InvalidVerdictError, match="structured_output"):
        ClaudeVerifier(process=process).verify(request_with_the_bundle_materialised(tmp_path))


def test_a_call_the_harness_declares_failed_is_rejected(tmp_path: Path) -> None:
    process = RecordedProcess(dict(payload("full-recipe")) | {"is_error": True})

    with pytest.raises(InvalidVerdictError, match="marked the call as failed"):
        ClaudeVerifier(process=process).verify(request_with_the_bundle_materialised(tmp_path))


def test_a_process_that_returns_no_json_is_rejected_with_what_it_left_on_stderr(tmp_path: Path) -> None:
    class BrokenProcess(Process):
        def run(self, argv: list[str], *, stdin: str) -> ProcessOutput:
            return ProcessOutput(code=1, stdout="", stderr="error: unknown option '--tools'")

    with pytest.raises(InvalidVerdictError, match="unknown option"):
        ClaudeVerifier(process=BrokenProcess()).verify(request_with_the_bundle_materialised(tmp_path))


def _finding_subschema() -> dict[str, object]:
    node: object = verdict_schema()
    for key in ("properties", "hallazgos", "items"):
        assert isinstance(node, dict)
        node = node[key]
    assert isinstance(node, dict)
    return node


def _contract_keys_of_every_field() -> set[str]:
    return {FINDING_CONTRACT_KEYS[f.name] for f in fields(Finding)}


def test_the_schema_declares_every_finding_field_of_the_domain_under_its_contract_key() -> None:
    properties = _finding_subschema()["properties"]

    assert isinstance(properties, dict)
    assert set(properties) == _contract_keys_of_every_field()


def test_the_schema_requires_every_finding_field_but_the_line() -> None:
    required = _finding_subschema()["required"]

    assert isinstance(required, list)
    assert set(required) == _contract_keys_of_every_field() - {FINDING_CONTRACT_KEYS["line"]}
