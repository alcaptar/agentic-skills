from __future__ import annotations

import json

import pytest

from slice_runner.domain.exceptions import InvalidImplementationReportError, PermissionDeniedError
from slice_runner.domain.path_kind import PathKind
from slice_runner.infrastructure.claude_implementer import ClaudeImplementer
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.slice_implementer_brief import SliceImplementerBrief
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import RecordedProcess
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother

_REPO = "/repos/project"
_RECORDED = "implementer-two-paths"


class TestHowTheImplementerIsInvoked:
    @pytest.fixture
    def argv(self) -> Argv:
        return Argv(ImplementerInvocation(repo=_REPO).argv)

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
        invocation = ImplementerInvocation(repo=_REPO)

        assert invocation.text == SliceImplementerBrief.TEXT
        assert invocation.text not in invocation.argv

    def test_the_cwd_the_process_needs_travels_with_the_invocation_and_not_only_as_a_bare_repo(self) -> None:
        assert ImplementerInvocation(repo=_REPO).cwd == _REPO


class TestWhereTheProcessRuns:
    def test_the_repo_becomes_the_working_directory_of_the_process_and_not_only_prompt_text(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        ClaudeImplementer(process=process).implement(repo=_REPO)

        assert process.cwd == _REPO

    def test_the_brief_is_what_travels_on_standard_input(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        ClaudeImplementer(process=process).implement(repo=_REPO)

        assert process.stdin == SliceImplementerBrief.TEXT


class TestTheReportOfARecordedCall:
    def test_both_paths_of_the_recorded_call_arrive_labelled(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        report = ClaudeImplementer(process=process).implement(repo=_REPO)

        assert [(reported.path, reported.kind) for reported in report.paths] == [
            ("hello.py", PathKind.PRODUCTION),
            ("test_hello.py", PathKind.TEST),
        ]

    def test_what_was_left_out_travels_whole(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        report = ClaudeImplementer(process=process).implement(repo=_REPO)

        assert report.left_out == "Nada; python3 -m pytest estaba disponible y el test paso correctamente."

    def test_what_the_harness_spent_on_the_call_travels_with_the_report(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        report = ClaudeImplementer(process=process).implement(repo=_REPO)

        assert report.spend == HarnessSpendMother.of_the_implementer_call()


class TestANonEmptyPermissionDenialsFailsTheCall:
    def test_a_denied_read_raises_instead_of_returning_a_report(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read_over(_RECORDED))

        with pytest.raises(PermissionDeniedError):
            ClaudeImplementer(process=process).implement(repo=_REPO)

    def test_the_error_names_which_permission_was_denied(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read_over(_RECORDED))

        with pytest.raises(PermissionDeniedError, match=f"Read {HarnessEnvelopeMother.DENIED_READ}"):
            ClaudeImplementer(process=process).implement(repo=_REPO)

    def test_what_the_denied_call_spent_survives_the_rejection(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read_over(_RECORDED))

        with pytest.raises(PermissionDeniedError) as rejection:
            ClaudeImplementer(process=process).implement(repo=_REPO)

        assert rejection.value.spend == HarnessSpendMother.of_the_implementer_call()


class TestWhatTheImplementerIsAllowedToReturn:
    def test_a_report_missing_a_required_field_is_rejected_instead_of_defaulted(self) -> None:
        incomplete: dict[str, object] = {"paths": [{"path": "hello.py", "kind": "production"}]}
        process = RecordedProcess(HarnessEnvelopeMother.carrying(incomplete, recorded=_RECORDED))

        with pytest.raises(InvalidImplementationReportError, match="left_out"):
            ClaudeImplementer(process=process).implement(repo=_REPO)

    def test_a_rejected_report_still_reports_what_the_call_spent(self) -> None:
        incomplete: dict[str, object] = {"paths": [{"path": "hello.py", "kind": "production"}]}
        process = RecordedProcess(HarnessEnvelopeMother.carrying(incomplete, recorded=_RECORDED))

        with pytest.raises(InvalidImplementationReportError) as rejection:
            ClaudeImplementer(process=process).implement(repo=_REPO)

        assert rejection.value.spend == HarnessSpendMother.of_the_implementer_call()

    def test_a_path_kind_outside_the_vocabulary_is_rejected_saying_which_one_it_was(self) -> None:
        invented_kind: dict[str, object] = {
            "paths": [{"path": "hello.py", "kind": "documentation"}],
            "left_out": "nothing",
        }
        process = RecordedProcess(HarnessEnvelopeMother.carrying(invented_kind, recorded=_RECORDED))

        with pytest.raises(InvalidImplementationReportError, match="'documentation'"):
            ClaudeImplementer(process=process).implement(repo=_REPO)
