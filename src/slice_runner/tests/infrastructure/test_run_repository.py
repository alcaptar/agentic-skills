from __future__ import annotations

import json
import re

import pytest

from slice_runner.domain.control_command import ControlCommand
from slice_runner.domain.exceptions import (
    EmptyIssueBodyError,
    LaggingSearchIndexError,
    MalformedConventionLineError,
    UnreadableIssueError,
    UnreadableRunError,
)
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.source import Source, SourceKind
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.infrastructure.run_repository import GhCommandFailedError, RunRepository
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import ScriptedProcess
from slice_runner.tests.mothers.gh_response_mother import GhResponseMother
from slice_runner.tests.mothers.run_mother import RunMother

_REPO = "alcaptar/agentic-skills"
_OTHER_REPO = "alcaptar/otro-repo"

_SUB2_BODY = (
    "REPO: alcaptar/otro-repo\n"
    "INTENCION: comprobar que el orden sale del titulo y no de la interfaz de programacion\n"
    "ACEPTACION: se ordena por slice-NN aunque la api la devuelva antes\n"
    "SENAL: exenta - spike de medicion\n"
)

_SUB1_BODY = (
    "INTENCION: hoy no hay forma de medir el formato nuevo sin crearlo\n"
    "ACEPTACION: el cuerpo se lee entero; los criterios llegan como lineas\n"
    "ACEPTACION: el bloque de estado se puede reescribir sin tocar lo de arriba\n"
    "SENAL: exenta - spike de medicion\n"
    "\n"
    "<!-- slice-runner:estado\n"
    '{"step": "await-ci", "control_retries": 1, "verify_retries": 0, "ci_retries": 0, '
    '"indeterminate_ticks": 2, "verify_discards": 0}\n'
    "-->\n\n"
)


class TestReadingTheParent:
    @staticmethod
    def _process() -> ScriptedProcess:
        recorded = GhResponseMother.parent_with_two_children()

        return ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(recorded), stderr=""))

    def test_it_asks_gh_for_exactly_the_fields_it_reads(self) -> None:
        process = self._process()

        RunRepository(process=process).read_parent(repo=_REPO, issue=43, slice_repo=None)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:4] == ["gh", "issue", "view", "43"]
        assert argv.value_of("--repo") == _REPO
        assert argv.value_of("--json") == "body,subIssuesSummary"

    def test_the_intention_is_the_text_of_its_own_section(self) -> None:
        parent = RunRepository(process=self._process()).read_parent(repo=_REPO, issue=43, slice_repo=None)

        assert parent.intention == "Spike de medicion del formato de subissues. Este issue se borra al terminar."

    def test_sources_with_no_repo_line_belong_to_the_issue_own_repo(self) -> None:
        parent = RunRepository(process=self._process()).read_parent(repo=_REPO, issue=43, slice_repo=None)

        assert parent.sources == (Source(kind=SourceKind.DOC, path="CLAUDE.md"),)

    def test_sources_under_a_repo_subsection_only_surface_when_that_repo_is_asked_for(self) -> None:
        parent = RunRepository(process=self._process()).read_parent(repo=_REPO, issue=43, slice_repo=_OTHER_REPO)

        assert parent.sources == (Source(kind=SourceKind.DOC, path="templates/CLAUDE.md"),)

    def test_controls_are_filtered_by_repo_the_same_way_sources_are(self) -> None:
        parent = RunRepository(process=self._process()).read_parent(repo=_REPO, issue=43, slice_repo=None)

        assert parent.controls == (
            ControlCommand(name="lint", command="make linting"),
            ControlCommand(name="tests", command="make test"),
        )

    def test_the_exemption_line_of_another_repo_is_still_a_control_command_once_filtered_to_it(self) -> None:
        parent = RunRepository(process=self._process()).read_parent(repo=_REPO, issue=43, slice_repo=_OTHER_REPO)

        assert parent.controls == (
            ControlCommand(name="ninguno", command="la integracion continua solo publica en master"),
        )

    def test_the_subissue_count_is_the_graphs_witness_not_something_counted_here(self) -> None:
        parent = RunRepository(process=self._process()).read_parent(repo=_REPO, issue=43, slice_repo=None)

        assert parent.subissue_count == 2

    @staticmethod
    def _process_with_body(body: str) -> ScriptedProcess:
        payload = {"body": body, "subIssuesSummary": {"completed": 0, "percentCompleted": 0, "total": 1}}

        return ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(payload), stderr=""))

    def test_a_dash_line_under_sources_that_does_not_match_the_source_format_is_rejected_not_dropped(self) -> None:
        body = "## Fuentes de convencion\n- CLAUDE.md\n"
        process = self._process_with_body(body)

        with pytest.raises(MalformedConventionLineError, match=re.escape("- CLAUDE.md")):
            RunRepository(process=process).read_parent(repo=_REPO, issue=43, slice_repo=None)

    def test_a_dash_line_under_controls_that_does_not_match_the_control_format_is_rejected_not_dropped(self) -> None:
        body = "## Controles\n- lint make linting\n"
        process = self._process_with_body(body)

        with pytest.raises(MalformedConventionLineError, match=re.escape("- lint make linting")):
            RunRepository(process=process).read_parent(repo=_REPO, issue=43, slice_repo=None)

    def test_a_blank_line_under_sources_does_not_raise(self) -> None:
        body = "## Fuentes de convencion\n- doc: CLAUDE.md\n\n\n## Controles\n- lint: make linting\n"
        process = self._process_with_body(body)

        parent = RunRepository(process=process).read_parent(repo=_REPO, issue=43, slice_repo=None)

        assert parent.sources == (Source(kind=SourceKind.DOC, path="CLAUDE.md"),)

    def test_a_repo_subsection_heading_under_controls_does_not_raise(self) -> None:
        body = (
            "## Fuentes de convencion\n- doc: CLAUDE.md\n"
            "## Controles\n- lint: make linting\n\n### alcaptar/otro-repo\n- ninguno: solo publica en master\n"
        )
        process = self._process_with_body(body)

        parent = RunRepository(process=process).read_parent(repo=_REPO, issue=43, slice_repo=_OTHER_REPO)

        assert parent.controls == (ControlCommand(name="ninguno", command="solo publica en master"),)


class TestReadingTheChildren:
    @staticmethod
    def _process(*, children: list[dict[str, object]] | None = None) -> ScriptedProcess:
        payload = children if children is not None else GhResponseMother.children_of_parent()

        return ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(payload), stderr=""))

    def test_it_searches_for_this_exact_parent_issue_and_asks_for_only_the_fields_it_reads(self) -> None:
        process = self._process()

        RunRepository(process=process).read_children(repo=_REPO, parent=43, expected=2)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:3] == ["gh", "issue", "list"]
        assert argv.value_of("--search") == f"parent-issue:{_REPO}#43"
        assert argv.value_of("--json") == "number,title,body,labels"

    def test_ordering_is_by_the_slice_number_in_the_title_not_by_the_order_the_search_returned(self) -> None:
        out_of_order = [
            {"number": 1, "title": "slice-02 (b): later slice, first in the response", "body": "", "labels": []},
            {"number": 2, "title": "slice-01 (a): earlier slice, last in the response", "body": "", "labels": []},
        ]

        children = RunRepository(process=self._process(children=out_of_order)).read_children(
            repo=_REPO, parent=43, expected=2
        )

        assert [child.slice_id for child in children] == ["slice-01", "slice-02"]

    def test_the_repo_line_of_the_body_becomes_the_subissue_repo(self) -> None:
        children = RunRepository(process=self._process()).read_children(repo=_REPO, parent=43, expected=2)

        by_slice = {child.slice_id: child for child in children}
        assert by_slice["slice-01"].repo is None
        assert by_slice["slice-02"].repo == _OTHER_REPO

    def test_a_body_with_no_state_block_reads_as_no_run_yet(self) -> None:
        children = RunRepository(process=self._process()).read_children(repo=_REPO, parent=43, expected=2)

        by_slice = {child.slice_id: child for child in children}
        assert by_slice["slice-02"].run is None

    def test_a_body_with_a_state_block_reads_the_run_it_holds(self) -> None:
        children = RunRepository(process=self._process()).read_children(repo=_REPO, parent=43, expected=2)

        by_slice = {child.slice_id: child for child in children}
        assert by_slice["slice-01"].run == RunMother.awaiting_ci()

    def test_the_macro_state_label_present_on_the_issue_is_read_as_the_issue_label(self) -> None:
        children = RunRepository(process=self._process()).read_children(repo=_REPO, parent=43, expected=2)

        by_slice = {child.slice_id: child for child in children}
        assert by_slice["slice-01"].label is IssueLabel.IN_PROGRESS
        assert by_slice["slice-02"].label is IssueLabel.PENDING

    def test_a_search_that_returns_fewer_subissues_than_the_graph_knows_about_raises_instead_of_deciding_short(
        self,
    ) -> None:
        with pytest.raises(LaggingSearchIndexError):
            RunRepository(process=self._process()).read_children(repo=_REPO, parent=43, expected=3)

    def test_a_subissue_title_with_no_slice_identifier_is_rejected_instead_of_sorted_arbitrarily(self) -> None:
        malformed = [{"number": 1, "title": "an issue with no slice id", "body": "", "labels": []}]

        with pytest.raises(UnreadableIssueError, match="slice-NN"):
            RunRepository(process=self._process(children=malformed)).read_children(repo=_REPO, parent=43, expected=1)

    def test_a_state_block_that_is_not_valid_json_is_rejected_as_unreadable(self) -> None:
        malformed = [
            {
                "number": 1,
                "title": "slice-01 (x): y",
                "body": "INTENCION: z\n\n<!-- slice-runner:estado\n{not json}\n-->\n",
                "labels": [],
            }
        ]

        with pytest.raises(UnreadableRunError):
            RunRepository(process=self._process(children=malformed)).read_children(repo=_REPO, parent=43, expected=1)


class TestWritingTheExecutionStateBlock:
    @staticmethod
    def _process(*, body: str, edit_code: int = 0) -> ScriptedProcess:
        return ScriptedProcess(
            ProcessOutput(code=0, stdout=json.dumps({"body": body}), stderr=""),
            ProcessOutput(code=edit_code, stdout="", stderr=""),
        )

    def test_a_body_with_no_block_yet_gets_one_appended_after_the_prose(self) -> None:
        process = self._process(body=_SUB2_BODY)

        RunRepository(process=process).write_run(repo=_OTHER_REPO, issue=44, run=RunMother.implementing())

        assert process.calls[1].stdin == (
            "REPO: alcaptar/otro-repo\n"
            "INTENCION: comprobar que el orden sale del titulo y no de la interfaz de programacion\n"
            "ACEPTACION: se ordena por slice-NN aunque la api la devuelva antes\n"
            "SENAL: exenta - spike de medicion\n"
            "\n"
            "<!-- slice-runner:estado\n"
            '{"step": "implement", "control_retries": 0, "verify_retries": 0, "ci_retries": 0, '
            '"indeterminate_ticks": 0, "verify_discards": 0}\n'
            "-->\n"
        )

    def test_a_body_that_already_has_a_block_gets_only_the_block_replaced(self) -> None:
        process = self._process(body=_SUB1_BODY)

        RunRepository(process=process).write_run(repo=_REPO, issue=45, run=RunMother.awaiting_merge())

        assert process.calls[1].stdin == (
            "INTENCION: hoy no hay forma de medir el formato nuevo sin crearlo\n"
            "ACEPTACION: el cuerpo se lee entero; los criterios llegan como lineas\n"
            "ACEPTACION: el bloque de estado se puede reescribir sin tocar lo de arriba\n"
            "SENAL: exenta - spike de medicion\n"
            "\n"
            "<!-- slice-runner:estado\n"
            '{"step": "await-merge", "control_retries": 0, "verify_retries": 0, "ci_retries": 0, '
            '"indeterminate_ticks": 0, "verify_discards": 0}\n'
            "-->\n\n"
        )

    def test_writing_the_same_run_that_is_already_there_issues_no_edit_call(self) -> None:
        process = self._process(body=_SUB1_BODY)

        RunRepository(process=process).write_run(repo=_REPO, issue=45, run=RunMother.awaiting_ci())

        assert len(process.calls) == 1

    def test_reading_and_writing_only_ever_name_the_one_issue_being_updated(self) -> None:
        process = self._process(body=_SUB2_BODY)

        RunRepository(process=process).write_run(repo=_OTHER_REPO, issue=44, run=RunMother.implementing())

        assert all("44" in call.argv for call in process.calls)
        assert all("45" not in call.argv for call in process.calls)

    def test_a_body_that_came_back_empty_is_rejected_before_the_edit_that_would_erase_the_prose(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps({"body": ""}), stderr=""))

        with pytest.raises(EmptyIssueBodyError):
            RunRepository(process=process).write_run(repo=_REPO, issue=45, run=RunMother.awaiting_ci())

        assert len(process.calls) == 1


class TestWritingTheMacroStateLabel:
    def test_a_normal_transition_is_a_single_call_that_both_adds_and_removes(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        RunRepository(process=process).write_label(
            repo=_REPO, issue=45, remove=IssueLabel.PENDING, add=IssueLabel.IN_PROGRESS
        )

        assert len(process.calls) == 1
        argv = Argv(process.calls[0].argv)
        assert argv.value_of("--add-label") == "estado:en-curso"
        assert argv.value_of("--remove-label") == "estado:pendiente"

    def test_the_only_issue_number_a_label_write_ever_names_is_the_one_being_transitioned(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        RunRepository(process=process).write_label(
            repo=_REPO, issue=45, remove=IssueLabel.PENDING, add=IssueLabel.IN_PROGRESS
        )

        assert all("44" not in call.argv for call in process.calls)
        assert all("45" in call.argv for call in process.calls)

    def test_it_never_reads_or_writes_a_body_because_a_macro_transition_is_a_label_write_only(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        RunRepository(process=process).write_label(
            repo=_REPO, issue=45, remove=IssueLabel.PENDING, add=IssueLabel.IN_PROGRESS
        )

        assert process.calls[0].argv[1:3] == ["issue", "edit"]
        assert "--body" not in process.calls[0].argv
        assert "--body-file" not in process.calls[0].argv
        assert "view" not in process.calls[0].argv

    def test_a_label_missing_on_the_repo_is_created_once_and_the_edit_is_retried(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(
                code=1,
                stdout="",
                stderr=(
                    "failed to update https://github.com/alcaptar/agentic-skills/issues/45: "
                    "'bloqueada:ci-roja' not found\nfailed to update 1 issue\n"
                ),
            ),
            ProcessOutput(code=0, stdout="", stderr=""),
            ProcessOutput(code=0, stdout="", stderr=""),
        )

        RunRepository(process=process).write_label(
            repo=_REPO, issue=45, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_CI_RED
        )

        assert len(process.calls) == 3
        assert process.calls[1].argv[:3] == ["gh", "label", "create"]
        assert process.calls[1].argv[3] == "bloqueada:ci-roja"
        assert Argv(process.calls[1].argv).value_of("--repo") == _REPO
        assert process.calls[2].argv == process.calls[0].argv

    def test_a_second_failure_after_creating_the_label_still_raises(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(code=1, stdout="", stderr="'bloqueada:ci-roja' not found"),
            ProcessOutput(code=0, stdout="", stderr=""),
            ProcessOutput(code=1, stdout="", stderr="rate limited"),
        )

        with pytest.raises(GhCommandFailedError):
            RunRepository(process=process).write_label(
                repo=_REPO, issue=45, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_CI_RED
            )

    def test_a_failure_unrelated_to_a_missing_label_raises_without_trying_to_create_one(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="authentication required"))

        with pytest.raises(GhCommandFailedError):
            RunRepository(process=process).write_label(
                repo=_REPO, issue=45, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_CI_RED
            )

        assert len(process.calls) == 1


class TestGhFailuresAreInterpretedNotSwallowed:
    def test_a_non_zero_exit_reading_the_parent_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="HTTP 404: Not Found"))

        with pytest.raises(GhCommandFailedError, match="HTTP 404"):
            RunRepository(process=process).read_parent(repo=_REPO, issue=999, slice_repo=None)

    def test_a_response_that_is_not_json_is_rejected_instead_of_crashing_on_a_decode_error(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="not json at all", stderr=""))

        with pytest.raises(UnreadableIssueError):
            RunRepository(process=process).read_parent(repo=_REPO, issue=43, slice_repo=None)
