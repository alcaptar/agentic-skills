from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import InvalidImplementationReportError, PermissionDeniedError
from slice_runner.domain.path_kind import PathKind
from slice_runner.domain.step import Step
from slice_runner.infrastructure.claude_implementer import ClaudeImplementer
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.slice_implementer_brief import SliceImplementerBrief
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import RecordedProcess, RecordedTrace, RecordedTurnLog, StreamingProcess
from slice_runner.tests.mothers.assignment_mother import AssignmentMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.implementation import Implementation
    from slice_runner.infrastructure.process import Process

_RECORDED = "implementer-two-paths"


class OneRound:
    @staticmethod
    def implemented(process: Process) -> Implementation:
        return ClaudeImplementer(process=process, trace=RecordedTrace(), turns=RecordedTurnLog()).implement(
            AssignmentMother.of_the_first_round()
        )


class TestHowTheImplementerIsInvoked:
    @pytest.fixture
    def argv(self) -> Argv:
        return Argv(ImplementerInvocation(assignment=AssignmentMother.of_the_first_round()).argv)

    def test_it_runs_with_bypassed_permissions_because_it_writes_and_runs_commands(self, argv: Argv) -> None:
        assert argv.value_of("--permission-mode") == "bypassPermissions"

    def test_the_model_is_fixed_and_not_inherited_from_whoever_launches_the_run(self, argv: Argv) -> None:
        assert argv.value_of("--model") == "sonnet"

    def test_the_tools_travel_in_a_single_comma_separated_argument(self, argv: Argv) -> None:
        assert argv.value_of("--tools") == "Read,Write,Edit,Bash,Grep,Glob,Skill"

    def test_skill_is_granted_because_the_brief_loads_the_methodology_skill(self, argv: Argv) -> None:
        assert "Skill" in argv.value_of("--tools").split(",")
        assert "test-driven-development" in SliceImplementerBrief.TEXT

    def test_the_mcp_servers_are_bounded(self, argv: Argv) -> None:
        assert argv.contains("--strict-mcp-config")

    def test_the_streamed_envelope_of_the_harness_is_asked_for_so_its_turns_can_be_watched_as_they_happen(
        self, argv: Argv
    ) -> None:
        assert argv.value_of("--output-format") == "stream-json"
        assert argv.contains("--verbose")

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
                "left_out": {"items": {"type": "string"}, "type": "array"},
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

        ClaudeImplementer(process=process, trace=RecordedTrace(), turns=RecordedTurnLog()).implement(
            AssignmentMother.of_the_first_round()
        )

        assert process.cwd == AssignmentMother.REPO


class TestTheSliceDataThatTravelsWithTheBrief:
    @staticmethod
    def _sent(assignment: Assignment) -> str:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        ClaudeImplementer(process=process, trace=RecordedTrace(), turns=RecordedTurnLog()).implement(assignment)

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

    def test_a_round_that_comes_back_from_red_controls_carries_the_path_of_the_log_and_never_its_output(self) -> None:
        assert self._sent(AssignmentMother.of_a_round_after_red_controls()).endswith(
            "- logs de los controles en rojo (1):\n  - /tmp/slice-runner/logs/lint.log"
        )

    def test_a_repo_exempt_from_controls_carries_its_reason_and_no_command_to_run(self) -> None:
        assert "- controles del repo: ninguno - la integracion continua solo publica en master\n" in self._sent(
            AssignmentMother.of_a_repo_exempt_from_controls()
        )


class TestTheReportOfARecordedCall:
    def test_both_paths_of_the_recorded_call_arrive_labelled(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        report = OneRound.implemented(process)

        assert [(reported.path, reported.kind) for reported in report.paths] == [
            ("hello.py", PathKind.PRODUCTION),
            ("test_hello.py", PathKind.TEST),
        ]

    def test_a_report_with_nothing_left_out_carries_an_empty_tuple(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        report = OneRound.implemented(process)

        assert report.left_out == ()

    def test_what_was_left_out_travels_whole_one_entry_per_thing(self) -> None:
        left_out: dict[str, object] = {
            "paths": [{"path": "hello.py", "kind": "production"}, {"path": "test_hello.py", "kind": "test"}],
            "left_out": [
                "el cableado del subcomando de metrics queda para otra slice",
                "no se anadio retry al cliente de gh",
            ],
        }
        process = RecordedProcess(HarnessEnvelopeMother.carrying(left_out, recorded=_RECORDED))

        report = OneRound.implemented(process)

        assert report.left_out == (
            "el cableado del subcomando de metrics queda para otra slice",
            "no se anadio retry al cliente de gh",
        )

    def test_what_the_harness_spent_on_the_call_travels_with_the_report(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        report = OneRound.implemented(process)

        assert report.spend == HarnessSpendMother.of_the_implementer_call()


class TestTheTraceOfTheCall:
    def test_the_session_the_call_ran_under_is_written_down_under_the_slice_and_the_step_it_served(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))
        trace = RecordedTrace()

        ClaudeImplementer(process=process, trace=trace, turns=RecordedTurnLog()).implement(
            AssignmentMother.of_the_first_round()
        )

        assert [(call.slice_id, call.step, call.session) for call in trace.calls] == [
            ("slice-05", Step.IMPLEMENT, HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER)
        ]

    def test_a_call_whose_report_is_rejected_is_traced_too_because_that_conversation_is_the_one_to_read(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read_over(_RECORDED))
        trace = RecordedTrace()

        with pytest.raises(PermissionDeniedError):
            ClaudeImplementer(process=process, trace=trace, turns=RecordedTurnLog()).implement(
                AssignmentMother.of_the_first_round()
            )

        assert [call.session for call in trace.calls] == [HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER]


class TestTheTurnsObservedWhileTheCallIsInFlight:
    def test_every_tool_use_of_a_real_streamed_call_is_observed_in_order_with_the_tool_and_its_target(self) -> None:
        process = StreamingProcess(HarnessEnvelopeMother.streamed())
        turns = RecordedTurnLog()

        ClaudeImplementer(process=process, trace=RecordedTrace(), turns=turns).implement(
            AssignmentMother.of_the_first_round()
        )

        assert [(turn.slice_id, turn.step, turn.number, turn.tool, turn.target) for turn in turns.turns] == [
            ("slice-05", Step.IMPLEMENT, 1, "Write", "/private/tmp/stream-capture2/repo/hello.py"),
            ("slice-05", Step.IMPLEMENT, 2, "StructuredOutput", None),
        ]

    def test_thinking_and_text_blocks_are_not_observed_because_they_name_no_tool(self) -> None:
        process = StreamingProcess(HarnessEnvelopeMother.streamed())
        turns = RecordedTurnLog()

        ClaudeImplementer(process=process, trace=RecordedTrace(), turns=turns).implement(
            AssignmentMother.of_the_first_round()
        )

        assert len(turns.turns) == 2

    def test_lines_that_are_not_an_assistant_turn_are_not_observed(self) -> None:
        process = StreamingProcess('{"type":"system","subtype":"init"}\n' + HarnessEnvelopeMother.streamed())
        turns = RecordedTurnLog()

        ClaudeImplementer(process=process, trace=RecordedTrace(), turns=turns).implement(
            AssignmentMother.of_the_first_round()
        )

        assert len(turns.turns) == 2

    def test_a_line_that_is_not_json_at_all_is_skipped_instead_of_raising(self) -> None:
        process = StreamingProcess("not json\n" + HarnessEnvelopeMother.streamed())
        turns = RecordedTurnLog()

        ClaudeImplementer(process=process, trace=RecordedTrace(), turns=turns).implement(
            AssignmentMother.of_the_first_round()
        )

        assert len(turns.turns) == 2

    def test_a_tool_use_block_whose_shape_this_program_cannot_read_is_skipped_instead_of_aborting_the_call(
        self,
    ) -> None:
        unreadable = json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "id": "x", "name": "Write", "input": "not-a-dict"}]},
            }
        )
        process = StreamingProcess(unreadable + "\n" + HarnessEnvelopeMother.streamed())
        turns = RecordedTurnLog()

        ClaudeImplementer(process=process, trace=RecordedTrace(), turns=turns).implement(
            AssignmentMother.of_the_first_round()
        )

        assert len(turns.turns) == 2


class TestANonEmptyPermissionDenialsFailsTheCall:
    def test_a_denied_read_raises_instead_of_returning_a_report(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read_over(_RECORDED))

        with pytest.raises(PermissionDeniedError):
            OneRound.implemented(process)

    def test_the_error_names_which_permission_was_denied(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read_over(_RECORDED))

        with pytest.raises(PermissionDeniedError, match=f"Read {HarnessEnvelopeMother.DENIED_READ}"):
            OneRound.implemented(process)

    def test_what_the_denied_call_spent_survives_the_rejection(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read_over(_RECORDED))

        with pytest.raises(PermissionDeniedError) as rejection:
            OneRound.implemented(process)

        assert rejection.value.spend == HarnessSpendMother.of_the_implementer_call()


class TestWhatTheImplementerIsAllowedToReturn:
    def test_a_report_missing_a_required_field_is_rejected_instead_of_defaulted(self) -> None:
        incomplete: dict[str, object] = {"paths": [{"path": "hello.py", "kind": "production"}]}
        process = RecordedProcess(HarnessEnvelopeMother.carrying(incomplete, recorded=_RECORDED))

        with pytest.raises(InvalidImplementationReportError, match="left_out"):
            OneRound.implemented(process)

    def test_a_rejected_report_still_reports_what_the_call_spent(self) -> None:
        incomplete: dict[str, object] = {"paths": [{"path": "hello.py", "kind": "production"}]}
        process = RecordedProcess(HarnessEnvelopeMother.carrying(incomplete, recorded=_RECORDED))

        with pytest.raises(InvalidImplementationReportError) as rejection:
            OneRound.implemented(process)

        assert rejection.value.spend == HarnessSpendMother.of_the_implementer_call()

    def test_a_path_kind_outside_the_vocabulary_is_rejected_saying_which_one_it_was(self) -> None:
        invented_kind: dict[str, object] = {
            "paths": [{"path": "hello.py", "kind": "documentation"}],
            "left_out": [],
        }
        process = RecordedProcess(HarnessEnvelopeMother.carrying(invented_kind, recorded=_RECORDED))

        with pytest.raises(InvalidImplementationReportError, match="'documentation'"):
            OneRound.implemented(process)
