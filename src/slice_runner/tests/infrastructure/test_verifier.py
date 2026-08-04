from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.verdict import Ruling
from slice_runner.infrastructure.verifier import ClaudeVerifier, JudgeInvocation
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import RecordedProcess
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother
from slice_runner.tests.mothers.verification_mother import VerificationRequestMother

if TYPE_CHECKING:
    from slice_runner.domain.verification import VerificationRequest

_BUNDLE = Path("/bundle")


class TestWhatTheJudgeIsGranted:
    @pytest.fixture
    def argv(self) -> Argv:
        return Argv(JudgeInvocation(request=VerificationRequestMother.with_the_bundle_in(_BUNDLE)).argv)

    def test_the_tools_travel_in_a_single_comma_separated_argument(self, argv: Argv) -> None:
        assert argv.value_of("--tools") == "Read,Grep,Glob,Skill"

    def test_the_judge_gets_skill_because_two_items_of_his_rubric_load_one(self, argv: Argv) -> None:
        assert "Skill" in argv.value_of("--tools").split(",")

    def test_no_writing_or_running_tools_because_the_one_who_verifies_does_not_implement(self, argv: Argv) -> None:
        granted = set(argv.value_of("--tools").split(","))

        assert granted.isdisjoint({"Bash", "Write", "Edit"})

    def test_tool_access_to_the_bundle_and_to_the_repo_he_has_to_read(self, argv: Argv) -> None:
        assert argv.values_of("--add-dir") == [str(_BUNDLE), VerificationRequestMother.REPO]

    def test_each_directory_travels_with_its_own_flag_so_the_argv_does_not_depend_on_its_arity(
        self, argv: Argv
    ) -> None:
        assert argv.occurrences_of("--add-dir") == 2

    def test_the_mcp_servers_are_bounded(self, argv: Argv) -> None:
        assert argv.contains("--strict-mcp-config")

    def test_the_json_envelope_of_the_harness_is_asked_for(self, argv: Argv) -> None:
        assert argv.value_of("--output-format") == "json"

    def test_the_verdict_schema_travels_declared(self, argv: Argv) -> None:
        assert "PASA" in argv.value_of("--json-schema")

    def test_no_value_follows_another_value_because_each_hangs_from_its_own_flag(self, argv: Argv) -> None:
        assert argv.executable == "claude"
        assert argv.values_that_follow_another_value() == []


class TestWhatTheJudgeIsTold:
    @pytest.fixture
    def request_of_the_run(self, tmp_path: Path) -> VerificationRequest:
        return VerificationRequestMother.with_the_bundle_in(tmp_path)

    def test_the_prompt_carries_the_rubric_and_the_paths_of_the_bundle(
        self, request_of_the_run: VerificationRequest
    ) -> None:
        prompt = JudgeInvocation(request=request_of_the_run).prompt

        assert request_of_the_run.instructions in prompt
        assert str(request_of_the_run.diff.slice_diff) in prompt
        assert str(request_of_the_run.diff.files) in prompt
        assert request_of_the_run.repo in prompt

    def test_the_prompt_travels_on_standard_input_and_not_in_the_argv(
        self, request_of_the_run: VerificationRequest
    ) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        ClaudeVerifier(process=process).verify(request_of_the_run)

        assert request_of_the_run.instructions in process.stdin
        assert process.stdin not in process.argv


class TestTheVerdictOfARealCall:
    @pytest.mark.parametrize("recorded", HarnessEnvelopeMother.RECORDED)
    def test_the_envelope_of_both_real_calls_is_read_whole_from_structured_output(
        self, recorded: str, tmp_path: Path
    ) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(recorded))

        verdict = ClaudeVerifier(process=process).verify(VerificationRequestMother.with_the_bundle_in(tmp_path))

        assert verdict.ruling is Ruling.FAIL
        assert len(verdict.findings) == 4

    def test_the_first_finding_of_the_recorded_call_arrives_whole(self, tmp_path: Path) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        verdict = ClaudeVerifier(process=process).verify(VerificationRequestMother.with_the_bundle_in(tmp_path))

        first = verdict.findings[0]
        assert (first.rule, first.path, first.line) == ("convenciones", "mod.py", 11)
