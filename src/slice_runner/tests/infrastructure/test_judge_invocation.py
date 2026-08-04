from __future__ import annotations

import json
from pathlib import Path

import pytest

from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.verdict_payload import VerdictPayload
from slice_runner.tests.argv import Argv
from slice_runner.tests.mothers.verification_mother import JudgePromptMother

_WRITTEN_TO = Path("/written-diff")


class TestWhatTheJudgeIsGranted:
    @pytest.fixture
    def argv(self) -> Argv:
        return Argv(JudgeInvocation(prompt=JudgePromptMother.with_the_diff_in(_WRITTEN_TO)).argv)

    def test_the_tools_travel_in_a_single_comma_separated_argument(self, argv: Argv) -> None:
        assert argv.value_of("--tools") == "Read,Grep,Glob,Skill"

    def test_the_judge_gets_skill_because_two_items_of_his_rubric_load_one(self, argv: Argv) -> None:
        assert "Skill" in argv.value_of("--tools").split(",")

    def test_no_writing_or_running_tools_because_the_one_who_verifies_does_not_implement(self, argv: Argv) -> None:
        granted = set(argv.value_of("--tools").split(","))

        assert granted.isdisjoint({"Bash", "Write", "Edit"})

    def test_tool_access_to_where_the_diff_was_written_and_to_the_repo_he_has_to_read(self, argv: Argv) -> None:
        assert argv.values_of("--add-dir") == [str(_WRITTEN_TO), JudgePromptMother.REPO]

    def test_each_directory_travels_with_its_own_flag_so_the_argv_does_not_depend_on_its_arity(
        self, argv: Argv
    ) -> None:
        assert argv.occurrences_of("--add-dir") == 2

    def test_the_mcp_servers_are_bounded(self, argv: Argv) -> None:
        assert argv.contains("--strict-mcp-config")

    def test_the_json_envelope_of_the_harness_is_asked_for(self, argv: Argv) -> None:
        assert argv.value_of("--output-format") == "json"

    def test_the_schema_that_travels_is_the_one_the_payload_generates_and_not_another(self, argv: Argv) -> None:
        assert json.loads(argv.value_of("--json-schema")) == VerdictPayload.json_schema()

    def test_no_value_follows_another_value_because_each_hangs_from_its_own_flag(self, argv: Argv) -> None:
        assert argv.executable == "claude"
        assert argv.values_that_follow_another_value() == []


class TestWhatTravelsOnStandardInput:
    def test_the_rubric_opens_it_so_the_run_data_reads_as_an_appendix_and_not_as_the_brief(self) -> None:
        prompt = JudgePromptMother.with_the_diff_in(_WRITTEN_TO)

        text = JudgeInvocation(prompt=prompt).text

        assert text.startswith(prompt.rubric)
        assert text.index("## Datos del run") > text.index(prompt.rubric)

    def test_it_carries_the_repo_and_where_the_diff_was_written(self) -> None:
        prompt = JudgePromptMother.with_the_diff_in(_WRITTEN_TO)

        text = JudgeInvocation(prompt=prompt).text

        assert prompt.repo in text
        assert str(prompt.diff.diff) in text

    def test_it_carries_the_scope_so_it_does_not_depend_on_the_judge_opening_a_file(self) -> None:
        prompt = JudgePromptMother.with_the_diff_in(_WRITTEN_TO, files=("src/a.py", "src/tests/test_a.py"))

        text = JudgeInvocation(prompt=prompt).text

        assert "src/a.py" in text
        assert "src/tests/test_a.py" in text
        assert "(2)" in text

    def test_the_prompt_does_not_also_travel_in_the_argv(self) -> None:
        invocation = JudgeInvocation(prompt=JudgePromptMother.with_the_diff_in(_WRITTEN_TO))

        assert invocation.text not in invocation.argv
