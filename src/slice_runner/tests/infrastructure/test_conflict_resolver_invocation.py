from __future__ import annotations

import json

import pytest

from slice_runner.infrastructure.conflict_resolution_report_payload import ConflictResolutionReportPayload
from slice_runner.infrastructure.conflict_resolver_brief import ConflictResolverBrief
from slice_runner.tests.argv import Argv
from slice_runner.tests.mothers.conflict_resolver_invocation_mother import ConflictResolverInvocationMother
from slice_runner.tests.mothers.merge_conflict_mother import MergeConflictMother


class TestHowTheConflictResolverCallIsInvoked:
    @pytest.fixture
    def argv(self) -> Argv:
        return Argv(ConflictResolverInvocationMother.of_one_conflicting_file().argv)

    def test_the_model_is_fixed_and_not_inherited_from_whoever_launches_the_run(self, argv: Argv) -> None:
        assert argv.value_of("--model") == "opus"

    def test_it_runs_with_bypassed_permissions_because_it_writes_to_the_conflicting_files(self, argv: Argv) -> None:
        assert argv.value_of("--permission-mode") == "bypassPermissions"

    def test_the_tools_travel_in_a_single_comma_separated_argument(self, argv: Argv) -> None:
        assert argv.value_of("--tools") == "Read,Write,Edit,Grep,Glob"

    def test_no_running_tools_because_resolving_a_conflict_is_not_running_a_command(self, argv: Argv) -> None:
        granted = set(argv.value_of("--tools").split(","))

        assert granted.isdisjoint({"Bash", "Skill"})

    def test_the_streamed_envelope_of_the_harness_is_asked_for_so_its_turns_can_be_watched_as_they_happen(
        self, argv: Argv
    ) -> None:
        assert argv.value_of("--output-format") == "stream-json"
        assert argv.contains("--verbose")

    def test_the_mcp_servers_are_bounded(self, argv: Argv) -> None:
        assert argv.contains("--strict-mcp-config")

    def test_only_user_settings_load_so_the_destination_repo_does_not_pay_its_own_claude_md(self, argv: Argv) -> None:
        assert argv.value_of("--setting-sources") == "user"

    def test_the_schema_that_travels_is_the_one_the_payload_generates_and_not_another(self, argv: Argv) -> None:
        assert json.loads(argv.value_of("--json-schema")) == ConflictResolutionReportPayload.json_schema()

    def test_no_value_follows_another_value_because_each_hangs_from_its_own_flag(self, argv: Argv) -> None:
        assert argv.executable == "claude"
        assert argv.values_that_follow_another_value() == []

    def test_the_brief_travels_on_standard_input_and_not_in_the_argv(self) -> None:
        invocation = ConflictResolverInvocationMother.of_one_conflicting_file()

        assert ConflictResolverBrief.TEXT in invocation.text
        assert invocation.text not in invocation.argv

    def test_the_cwd_the_process_needs_is_the_worktree_of_the_conflict(self) -> None:
        assert ConflictResolverInvocationMother.of_one_conflicting_file().cwd == MergeConflictMother.WORKTREE


class TestTheConflictDataThatTravelsWithTheBrief:
    def test_it_names_the_issue_the_slice_the_repo_the_branch_the_base_and_the_conflicting_paths(self) -> None:
        text = ConflictResolverInvocationMother.of_one_conflicting_file().text

        assert text.endswith(
            "## Datos del conflicto\n"
            "\n"
            f"- issue: #{MergeConflictMother.ISSUE}\n"
            f"- slice: {MergeConflictMother.SLICE_ID}\n"
            f"- repo: {MergeConflictMother.REPO}\n"
            f"- ruta del repo: {MergeConflictMother.WORKTREE}\n"
            f"- rama: {MergeConflictMother.BRANCH}\n"
            f"- base: {MergeConflictMother.BASE}\n"
            "- ficheros en conflicto (1):\n"
            "  - shared.txt\n"
            "- fuentes de convencion (1):\n"
            "  - doc: CLAUDE.md\n"
            "    reglas del repo"
        )

    def test_the_brief_opens_the_prompt_so_the_conflict_data_reads_as_an_appendix(self) -> None:
        assert ConflictResolverInvocationMother.of_one_conflicting_file().text.startswith(ConflictResolverBrief.TEXT)

    def test_a_conflict_with_no_sources_declared_still_names_the_heading_with_zero_of_them(self) -> None:
        text = ConflictResolverInvocationMother.without_sources().text

        assert text.endswith("- fuentes de convencion (0):")
