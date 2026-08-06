from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import InvalidImplementationReportError, PermissionDeniedError
from slice_runner.domain.path_kind import PathKind
from slice_runner.infrastructure.claude_implementer import ClaudeImplementer
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.slice_implementer_brief import SliceImplementerBrief
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import RecordedProcess
from slice_runner.tests.mothers.assignment_mother import AssignmentMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment

_RECORDED = "implementer-two-paths"


class TestHowTheImplementerIsInvoked:
    @pytest.fixture
    def argv(self) -> Argv:
        return Argv(ImplementerInvocation(assignment=AssignmentMother.of_the_first_round()).argv)

    def test_it_runs_with_bypassed_permissions_because_it_writes_and_runs_commands(self, argv: Argv) -> None:
        assert argv.value_of("--permission-mode") == "bypassPermissions"

    def test_the_tools_travel_in_a_single_comma_separated_argument(self, argv: Argv) -> None:
        assert argv.value_of("--tools") == "Read,Write,Edit,Bash,Grep,Glob,Skill"

    def test_skill_is_granted_because_the_brief_loads_the_methodology_skill(self, argv: Argv) -> None:
        assert "Skill" in argv.value_of("--tools").split(",")
        assert "test-driven-development" in SliceImplementerBrief.TEXT

    def test_the_mcp_servers_are_bounded(self, argv: Argv) -> None:
        assert argv.contains("--strict-mcp-config")

    def test_the_json_envelope_of_the_harness_is_asked_for(self, argv: Argv) -> None:
        assert argv.value_of("--output-format") == "json"

    def test_the_schema_that_travels_is_flat_with_the_enum_and_the_nested_object_resolved(self, argv: Argv) -> None:
        assert json.loads(argv.value_of("--json-schema")) == {
            "additionalProperties": False,
            "properties": {
                "paths": {
                    "items": {
                        "additionalProperties": False,
                        "properties": {
                            "path": {"type": "string"},
                            "kind": {"enum": ["production", "test"], "type": "string"},
                        },
                        "required": ["path", "kind"],
                        "type": "object",
                    },
                    "type": "array",
                },
                "left_out": {"type": "string"},
            },
            "required": ["paths", "left_out"],
            "type": "object",
        }

    def test_no_value_follows_another_value_because_each_hangs_from_its_own_flag(self, argv: Argv) -> None:
        assert argv.executable == "claude"
        assert argv.values_that_follow_another_value() == []

    def test_the_brief_travels_on_standard_input_and_not_in_the_argv(self) -> None:
        invocation = ImplementerInvocation(assignment=AssignmentMother.of_the_first_round())

        assert SliceImplementerBrief.TEXT in invocation.text
        assert invocation.text not in invocation.argv

    def test_the_cwd_the_process_needs_travels_with_the_invocation_and_not_only_as_a_bare_repo(self) -> None:
        assert ImplementerInvocation(assignment=AssignmentMother.of_the_first_round()).cwd == AssignmentMother.REPO


class TestWhereTheProcessRuns:
    def test_the_repo_becomes_the_working_directory_of_the_process_and_not_only_prompt_text(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        ClaudeImplementer(process=process).implement(AssignmentMother.of_the_first_round())

        assert process.cwd == AssignmentMother.REPO


class TestTheSliceDataThatTravelsWithTheBrief:
    @staticmethod
    def _sent(assignment: Assignment) -> str:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        ClaudeImplementer(process=process).implement(assignment)

        return process.stdin

    def test_the_methodology_opens_the_prompt_so_the_data_of_the_slice_reads_as_an_appendix(self) -> None:
        assert self._sent(AssignmentMother.of_the_first_round()).startswith(SliceImplementerBrief.TEXT)

    def test_a_first_round_says_which_slice_of_which_issue_it_is_and_everything_the_slice_declared(self) -> None:
        assert self._sent(AssignmentMother.of_the_first_round()).endswith(
            "## Datos de la slice\n"
            "\n"
            "- issue: #45\n"
            "- slice: slice-05\n"
            "- ruta del repo: /repos/agentic-skills\n"
            "- intencion: hoy nada evita reimplementar una slice ya entregada\n"
            "- senal: exenta - este repo no despliega\n"
            "- criterios de aceptacion (2):\n"
            "  - antes de tocar codigo comprueba que la subissue no este ya cerrada\n"
            "  - cada precheck falla con un motivo distinguible, no con un booleano\n"
            "- fuentes de convencion (1):\n"
            "  - doc: CLAUDE.md\n"
            "- controles del repo (1):\n"
            "  - lint: make linting\n"
            "- hallazgos de la vuelta anterior: ninguno, esta es la primera"
        )

    def test_a_second_round_carries_every_finding_with_where_it_was_raised_and_why(self) -> None:
        assert self._sent(AssignmentMother.of_a_second_round()).endswith(
            "- hallazgos de la vuelta anterior (1):\n"
            "  - [media] convenciones en src/x.py:42: prose in a `.py` "
            "(detalle: the why lives in the pull request body)"
        )

    def test_a_repo_exempt_from_controls_carries_its_reason_and_no_command_to_run(self) -> None:
        assert "- controles del repo: ninguno - la integracion continua solo publica en master\n" in self._sent(
            AssignmentMother.of_a_repo_exempt_from_controls()
        )


class TestTheReportOfARecordedCall:
    def test_both_paths_of_the_recorded_call_arrive_labelled(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        report = ClaudeImplementer(process=process).implement(AssignmentMother.of_the_first_round())

        assert [(reported.path, reported.kind) for reported in report.paths] == [
            ("hello.py", PathKind.PRODUCTION),
            ("test_hello.py", PathKind.TEST),
        ]

    def test_what_was_left_out_travels_whole(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        report = ClaudeImplementer(process=process).implement(AssignmentMother.of_the_first_round())

        assert report.left_out == "Nada; python3 -m pytest estaba disponible y el test paso correctamente."

    def test_the_cost_and_the_turns_of_the_harness_travel_with_the_report(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        report = ClaudeImplementer(process=process).implement(AssignmentMother.of_the_first_round())

        assert (report.cost_usd, report.turns) == (0.3433209, 9)


class TestANonEmptyPermissionDenialsFailsTheCall:
    def test_a_denied_read_raises_instead_of_returning_a_report(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read_over(_RECORDED))

        with pytest.raises(PermissionDeniedError):
            ClaudeImplementer(process=process).implement(AssignmentMother.of_the_first_round())

    def test_the_error_names_which_permission_was_denied(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read_over(_RECORDED))

        with pytest.raises(PermissionDeniedError, match=f"Read {HarnessEnvelopeMother.DENIED_READ}"):
            ClaudeImplementer(process=process).implement(AssignmentMother.of_the_first_round())


class TestWhatTheImplementerIsAllowedToReturn:
    def test_a_report_missing_a_required_field_is_rejected_instead_of_defaulted(self) -> None:
        incomplete: dict[str, object] = {"paths": [{"path": "hello.py", "kind": "production"}]}
        process = RecordedProcess(HarnessEnvelopeMother.carrying(incomplete, recorded=_RECORDED))

        with pytest.raises(InvalidImplementationReportError, match="left_out"):
            ClaudeImplementer(process=process).implement(AssignmentMother.of_the_first_round())

    def test_a_path_kind_outside_the_vocabulary_is_rejected_saying_which_one_it_was(self) -> None:
        invented_kind: dict[str, object] = {
            "paths": [{"path": "hello.py", "kind": "documentation"}],
            "left_out": "nothing",
        }
        process = RecordedProcess(HarnessEnvelopeMother.carrying(invented_kind, recorded=_RECORDED))

        with pytest.raises(InvalidImplementationReportError, match="'documentation'"):
            ClaudeImplementer(process=process).implement(AssignmentMother.of_the_first_round())
