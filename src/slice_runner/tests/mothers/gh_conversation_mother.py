from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.issue_state import IssueState

if TYPE_CHECKING:
    from slice_runner.domain.run import Run

_PARENT_BODY = (
    "## Intencion\n"
    "hoy conducir una slice todavia exige una sesion de chat.\n"
    "\n"
    "## Fuentes de convencion\n"
    "- doc: CLAUDE.md\n"
    "\n"
    "## Controles\n"
    "- lint: make linting\n"
)

_SUBISSUE_PROSE = (
    "INTENCION: hoy nada evita reimplementar una slice ya entregada\n"
    "ACEPTACION: el run retoma por el paso que dice el estado persistido\n"
    "SENAL: exenta - este repo no despliega\n"
)


class GhConversationMother:
    REPO: ClassVar[str] = "alcaptar/agentic-skills"
    WORKTREE: ClassVar[str] = "/repos/agentic-skills"
    BASE: ClassVar[str] = "master"
    ISSUE: ClassVar[int] = 38
    SUBISSUE: ClassVar[int] = 45
    SLICE: ClassVar[str] = "slice-05"
    NAME: ClassVar[str] = "prechecks-deterministas"
    SUMMARY: ClassVar[str] = "comprobar antes de tocar codigo"
    BRANCH: ClassVar[str] = "slice/05-prechecks-deterministas"
    PULL_REQUEST: ClassVar[int] = 61
    CONTROL: ClassVar[str] = "make linting"

    @classmethod
    def parent_of_one_slice(cls) -> str:
        return json.dumps(
            {"body": _PARENT_BODY, "subIssuesSummary": {"completed": 0, "percentCompleted": 0, "total": 1}}
        )

    @classmethod
    def body_of_the_subissue(cls) -> str:
        return json.dumps({"body": _SUBISSUE_PROSE})

    @classmethod
    def the_slice_resumed_at(cls, run: Run) -> str:
        return cls._children(
            body=f"{_SUBISSUE_PROSE}\n{cls._state_block(run)}\n", label=IssueLabel.IN_PROGRESS, state=IssueState.OPEN
        )

    @classmethod
    def the_slice_never_run(cls) -> str:
        return cls._children(body=_SUBISSUE_PROSE, label=IssueLabel.PENDING, state=IssueState.OPEN)

    @classmethod
    def the_slice_already_closed(cls) -> str:
        return cls._children(body=_SUBISSUE_PROSE, label=IssueLabel.PENDING, state=IssueState.CLOSED)

    @classmethod
    def a_title_that_names_no_slice(cls) -> str:
        return json.dumps(
            [
                {
                    "number": cls.SUBISSUE,
                    "title": "una subissue que nadie titulo como slice",
                    "body": _SUBISSUE_PROSE,
                    "labels": [],
                    "state": IssueState.OPEN.value,
                }
            ]
        )

    @classmethod
    def no_open_pull_request(cls) -> str:
        return json.dumps([])

    @classmethod
    def the_open_pull_request(cls) -> str:
        return json.dumps([{"number": cls.PULL_REQUEST}])

    @classmethod
    def the_pull_request_of_the_branch(cls) -> str:
        return json.dumps([{"number": cls.PULL_REQUEST}])

    @classmethod
    def a_merged_pull_request(cls) -> str:
        return json.dumps({"state": "MERGED"})

    @classmethod
    def a_pull_request_still_open(cls) -> str:
        return json.dumps({"state": "OPEN"})

    @classmethod
    def a_pull_request_closed_without_merging(cls) -> str:
        return json.dumps({"state": "CLOSED"})

    @classmethod
    def checks_in_red(cls) -> str:
        return json.dumps([{"name": "check", "bucket": "fail"}])

    @classmethod
    def _children(cls, *, body: str, label: IssueLabel, state: IssueState) -> str:
        return json.dumps(
            [
                {
                    "number": cls.SUBISSUE,
                    "title": f"{cls.SLICE} ({cls.NAME}): {cls.SUMMARY}",
                    "body": body,
                    "labels": [
                        {"id": "LA_kwDOThEBoM8AAAACu6gVcw", "name": label.value, "description": "", "color": "1d76db"}
                    ],
                    "state": state.value,
                }
            ]
        )

    @staticmethod
    def _state_block(run: Run) -> str:
        state = {
            "step": run.step.value,
            "control_retries": run.control_retries,
            "verify_retries": run.verify_retries,
            "ci_retries": run.ci_retries,
            "indeterminate_ticks": run.indeterminate_ticks,
            "verify_discards": run.verify_discards,
        }

        return f"<!-- slice-runner:estado\n{json.dumps(state)}\n-->"
