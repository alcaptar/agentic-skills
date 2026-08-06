from __future__ import annotations

import json

import pytest

from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.verdict_payload import VerdictPayload
from slice_runner.tests.argv import Argv
from slice_runner.tests.mothers.verification_mother import JudgeMother, SliceUnderReviewMother

_JUDGE = JudgeMother.reading_the_repo_and_its_yardstick()


class TestWhatTheJudgeIsGranted:
    @pytest.fixture
    def argv(self) -> Argv:
        return Argv(
            JudgeInvocation(
                judge=JudgeMother.reading_the_repo_and_its_yardstick(), review=SliceUnderReviewMother.of_the_slice()
            ).argv
        )

    def test_the_tools_travel_in_a_single_comma_separated_argument(self, argv: Argv) -> None:
        assert argv.value_of("--tools") == "Read,Grep,Glob,Skill"

    def test_the_judge_gets_skill_because_two_items_of_his_rubric_load_one(self, argv: Argv) -> None:
        assert "Skill" in argv.value_of("--tools").split(",")

    def test_no_writing_or_running_tools_because_the_one_who_verifies_does_not_implement(self, argv: Argv) -> None:
        granted = set(argv.value_of("--tools").split(","))

        assert granted.isdisjoint({"Bash", "Write", "Edit"})

    def test_the_only_directory_granted_is_the_repo_because_the_diff_is_no_longer_a_file_somewhere(
        self, argv: Argv
    ) -> None:
        assert argv.values_of("--add-dir") == [SliceUnderReviewMother.REPO, str(JudgeMother.YARDSTICK)]

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
        review = SliceUnderReviewMother.of_the_slice()

        text = JudgeInvocation(judge=_JUDGE, review=review).text

        assert text.startswith(_JUDGE.rubric)
        assert text.index("## Datos del run") > text.index(_JUDGE.rubric)

    def test_it_carries_the_repo_the_judge_still_has_to_read_around_the_diff(self) -> None:
        review = SliceUnderReviewMother.of_the_slice()

        assert review.repo in JudgeInvocation(judge=_JUDGE, review=review).text

    def test_the_diff_itself_travels_so_a_verdict_cannot_be_reached_without_having_been_shown_it(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(text="-    return 1\n+    return 2\n")

        assert "+    return 2" in JudgeInvocation(judge=_JUDGE, review=review).text

    def test_the_diff_closes_the_prompt_so_no_delimiter_has_to_survive_its_own_content(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(text='+_RUBRIC = """\\\n+```json\n+{}\n+```\n')

        text = JudgeInvocation(judge=_JUDGE, review=review).text

        assert text.endswith(review.diff.text)

    def test_it_carries_the_scope_so_it_does_not_depend_on_the_judge_reading_the_diff_the_same_way(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(files=("src/a.py", "src/tests/test_a.py"))

        text = JudgeInvocation(judge=_JUDGE, review=review).text

        assert "src/a.py" in text
        assert "src/tests/test_a.py" in text
        assert "(2)" in text

    def test_it_carries_the_slice_it_judges_with_the_yardstick_the_closed_rubric_measures_it_against(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(files=("src/a.py",))

        assert (
            "## Datos del run\n"
            "\n"
            "- slice: slice-05\n"
            "- ruta del repo: /repos/project\n"
            "- senal: exenta - este repo no despliega\n"
            "- criterios de aceptacion (2):\n"
            "  - antes de tocar codigo comprueba que la subissue no este ya cerrada\n"
            "  - cada precheck falla con un motivo distinguible, no con un booleano\n"
            "- fuentes de convencion (1):\n"
            "  - doc: CLAUDE.md\n"
            "- checklist de slices del issue (2):\n"
            "  - [CLOSED] slice-05 (prechecks-deterministas): comprobar antes de tocar codigo\n"
            "  - [OPEN] slice-06 (pausa-de-alineacion): el entendimiento se escribe siempre\n"
            "- ficheros que toca la slice (1):\n"
            "  - src/a.py\n"
            "- directorios que puedes leer (2):\n"
            "  - /repos/project\n"
            "  - /toolbox/skills\n"
        ) in JudgeInvocation(judge=_JUDGE, review=review).text

    def test_what_the_judge_may_read_is_labelled_apart_from_the_files_of_the_slice(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(files=("src/a.py",))

        text = JudgeInvocation(judge=_JUDGE, review=review).text

        assert text.index("src/a.py") < text.index("directorios que puedes leer")
        assert text.index("directorios que puedes leer") < text.index(str(JudgeMother.YARDSTICK))

    def test_the_prompt_does_not_also_travel_in_the_argv(self) -> None:
        invocation = JudgeInvocation(
            judge=JudgeMother.reading_the_repo_and_its_yardstick(), review=SliceUnderReviewMother.of_the_slice()
        )

        assert invocation.text not in invocation.argv
