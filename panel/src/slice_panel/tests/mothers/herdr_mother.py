from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from slice_panel.domain.process_outcome import ProcessOutcome
from slice_panel.tests.mothers.outcome_mother import OutcomeMother

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


class HerdrMother:
    PAYLOADS: ClassVar[Path] = Path(__file__).parent.parent / "payloads"
    TAB: ClassVar[str] = "w1:t2"
    PANE: ClassVar[str] = "w1:p3"
    WORKSPACE: ClassVar[str] = "w1"

    @classmethod
    def tab_created(cls) -> ProcessOutcome:
        body = {
            "id": "cli:tab:create",
            "result": {
                "tab": {"tab_id": cls.TAB, "workspace_id": cls.WORKSPACE},
                "root_pane": {"pane_id": cls.PANE},
                "type": "tab_created",
            },
        }

        return OutcomeMother.succeeded(json.dumps(body))

    @classmethod
    def tab_created_without_the_pane(cls) -> ProcessOutcome:
        body = {"id": "cli:tab:create", "result": {"tab": {"tab_id": cls.TAB}, "type": "tab_created"}}

        return OutcomeMother.succeeded(json.dumps(body))

    @classmethod
    def server_running(cls) -> ProcessOutcome:
        return OutcomeMother.succeeded((cls.PAYLOADS / "herdr_status_server_running.txt").read_text())

    @classmethod
    def server_stopped(cls, *, exit_code: int = 0) -> ProcessOutcome:
        stdout = (cls.PAYLOADS / "herdr_status_server_stopped.txt").read_text()

        return ProcessOutcome(exit_code=exit_code, stdout=stdout, stderr="")

    @classmethod
    def server_status_without_a_state(cls) -> ProcessOutcome:
        return OutcomeMother.succeeded("version: 0.9.3\n")

    @classmethod
    def server_status_with_an_unknown_state(cls) -> ProcessOutcome:
        return OutcomeMother.succeeded("status: starting\n")

    @classmethod
    def workspace_list(cls, labelled: Mapping[str, str]) -> ProcessOutcome:
        workspaces = [
            {"label": label, "workspace_id": workspace, "focused": False} for workspace, label in labelled.items()
        ]
        body = {"id": "cli:workspace:list", "result": {"type": "workspace_list", "workspaces": workspaces}}

        return OutcomeMother.succeeded(json.dumps(body))

    @classmethod
    def pane_list(cls, cwds: Sequence[str]) -> ProcessOutcome:
        panes = [
            {"pane_id": f"{cls.WORKSPACE}:p{number}", "cwd": cwd, "workspace_id": cls.WORKSPACE}
            for number, cwd in enumerate(cwds, 1)
        ]
        body = {"id": "cli:pane:list", "result": {"panes": panes, "type": "pane_list"}}

        return OutcomeMother.succeeded(json.dumps(body))

    @classmethod
    def workspace_created(cls) -> ProcessOutcome:
        body = {
            "id": "cli:workspace:create",
            "result": {
                "type": "workspace_created",
                "workspace": {"workspace_id": cls.WORKSPACE, "label": "clone"},
                "root_pane": {"pane_id": cls.PANE},
            },
        }

        return OutcomeMother.succeeded(json.dumps(body))

    @classmethod
    def workspace_created_without_the_pane(cls) -> ProcessOutcome:
        body = {"id": "cli:workspace:create", "result": {"workspace": {"workspace_id": cls.WORKSPACE}}}

        return OutcomeMother.succeeded(json.dumps(body))

    @classmethod
    def pane_split(cls, pane: str) -> ProcessOutcome:
        body = {"id": "cli:pane:split", "result": {"type": "pane_split", "pane": {"pane_id": pane}}}

        return OutcomeMother.succeeded(json.dumps(body))

    @classmethod
    def agent_name_taken_on_stdout(cls) -> ProcessOutcome:
        return ProcessOutcome(exit_code=1, stdout=cls._agent_name_taken_body(), stderr="")

    @classmethod
    def agent_name_taken_on_stderr(cls) -> ProcessOutcome:
        return ProcessOutcome(exit_code=1, stdout="", stderr=cls._agent_name_taken_body())

    @classmethod
    def other_herdr_error(cls) -> ProcessOutcome:
        body = {"id": "cli:agent:start", "error": {"code": "pane_not_found", "message": "pane w1:p3 not found"}}

        return ProcessOutcome(exit_code=1, stdout=json.dumps(body), stderr="")

    @staticmethod
    def _agent_name_taken_body() -> str:
        body = {
            "id": "cli:agent:start",
            "error": {"code": "agent_name_taken", "message": "agent name coordinador-clone is already in use"},
        }

        return json.dumps(body)
