from __future__ import annotations

import json

import pytest

from slice_runner.infrastructure.understanding_brief import UnderstandingBrief
from slice_runner.infrastructure.understanding_report_payload import UnderstandingReportPayload
from slice_runner.tests.argv import Argv
from slice_runner.tests.mothers.understanding_invocation_mother import UnderstandingInvocationMother

_REPO = UnderstandingInvocationMother.REPO
_WORKTREE = UnderstandingInvocationMother.WORKTREE


class TestHowTheUnderstandingCallIsInvoked:
    @pytest.fixture
    def argv(self) -> Argv:
        return Argv(UnderstandingInvocationMother.of_the_chosen_slice().argv)

    def test_the_model_is_fixed_and_not_inherited_from_whoever_launches_the_run(self, argv: Argv) -> None:
        assert argv.value_of("--model") == "sonnet"

    def test_the_tools_travel_in_a_single_comma_separated_argument(self, argv: Argv) -> None:
        assert argv.value_of("--tools") == "Read,Grep,Glob,Skill"

    def test_no_writing_or_running_tools_because_understanding_is_not_implementing(self, argv: Argv) -> None:
        granted = set(argv.value_of("--tools").split(","))

        assert granted.isdisjoint({"Bash", "Write", "Edit"})

    def test_the_json_envelope_of_the_harness_is_asked_for_because_no_turn_needs_watching(self, argv: Argv) -> None:
        assert argv.value_of("--output-format") == "json"

    def test_the_mcp_servers_are_bounded(self, argv: Argv) -> None:
        assert argv.contains("--strict-mcp-config")

    def test_the_schema_that_travels_is_the_one_the_payload_generates_and_not_another(self, argv: Argv) -> None:
        assert json.loads(argv.value_of("--json-schema")) == UnderstandingReportPayload.json_schema()

    def test_no_value_follows_another_value_because_each_hangs_from_its_own_flag(self, argv: Argv) -> None:
        assert argv.executable == "claude"
        assert argv.values_that_follow_another_value() == []

    def test_the_brief_travels_on_standard_input_and_not_in_the_argv(self) -> None:
        invocation = UnderstandingInvocationMother.of_the_chosen_slice()

        assert UnderstandingBrief.TEXT in invocation.text
        assert invocation.text not in invocation.argv

    def test_the_cwd_the_process_needs_is_the_worktree_and_not_the_gh_repo_slug(self) -> None:
        assert UnderstandingInvocationMother.of_the_chosen_slice().cwd == _WORKTREE


class TestTheSliceDataThatTravelsWithTheBrief:
    def test_it_names_the_issue_the_slice_the_repo_and_the_rama_the_branch_will_get(self) -> None:
        text = UnderstandingInvocationMother.of_the_chosen_slice().text

        assert text.endswith(
            "## Datos de la slice\n"
            "\n"
            "- issue: #45\n"
            "- slice: slice-05\n"
            f"- repo: {_REPO}\n"
            "- rama: slice/05-prechecks-deterministas\n"
            f"- ruta del repo: {_WORKTREE}\n"
            "- intencion: hoy nada evita reimplementar una slice ya entregada\n"
            "- senal: exenta - este repo no despliega\n"
            "- criterios de aceptacion (2):\n"
            "  - antes de tocar codigo comprueba que la subissue no este ya cerrada\n"
            "  - cada precheck falla con un motivo distinguible, no con un booleano\n"
            "- fuentes de convencion (1):\n"
            "  - doc: CLAUDE.md\n"
            "- controles del repo (1):\n"
            "  - lint: make linting"
        )

    def test_the_brief_opens_the_prompt_so_the_data_of_the_slice_reads_as_an_appendix(self) -> None:
        assert UnderstandingInvocationMother.of_the_chosen_slice().text.startswith(UnderstandingBrief.TEXT)

    def test_a_repo_exempt_from_controls_carries_its_reason_and_no_command_to_run(self) -> None:
        text = UnderstandingInvocationMother.of_a_repo_exempt_from_controls().text

        assert text.endswith("- controles del repo: ninguno - la integracion continua solo publica en master")
