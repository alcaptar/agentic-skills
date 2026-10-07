from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from slice_panel.domain.exceptions import AgentNameTakenError, ProcessTimedOutError
from slice_panel.domain.server_state import ServerState
from slice_panel.infrastructure.herdr_payload_rejected import HerdrPayloadRejectedError
from slice_panel.infrastructure.herdr_tabs import HerdrFailedError
from slice_panel.infrastructure.herdr_workspace_host import HerdrWorkspaceHost
from slice_panel.tests.doubles import AttachedToTheSessionError, RecordingLauncher, RecordingUnboundedProcesses
from slice_panel.tests.mothers.herdr_mother import HerdrMother
from slice_panel.tests.mothers.outcome_mother import OutcomeMother

if TYPE_CHECKING:
    from slice_panel.domain.process_outcome import ProcessOutcome

STATUS = ("herdr", "status", "server")


class WithAHost:
    @staticmethod
    def host(launcher: RecordingLauncher, unbounded: RecordingUnboundedProcesses | None = None) -> HerdrWorkspaceHost:
        return HerdrWorkspaceHost(launcher=launcher, unbounded=unbounded or RecordingUnboundedProcesses())


class TestTheServerState(WithAHost):
    async def test_a_recorded_running_status_is_read_as_running(self) -> None:
        launcher = RecordingLauncher({STATUS: HerdrMother.server_running()})

        assert await self.host(launcher).server_state() is ServerState.RUNNING

    async def test_a_recorded_stopped_status_is_read_as_stopped_even_when_the_command_exits_non_zero(self) -> None:
        launcher = RecordingLauncher({STATUS: HerdrMother.server_stopped(exit_code=1)})

        assert await self.host(launcher).server_state() is ServerState.STOPPED

    @pytest.mark.parametrize(
        "answer", [HerdrMother.server_status_without_a_state(), HerdrMother.server_status_with_an_unknown_state()]
    )
    async def test_a_status_that_names_no_known_state_is_rejected_instead_of_guessed(
        self, answer: ProcessOutcome
    ) -> None:
        launcher = RecordingLauncher({STATUS: answer})

        with pytest.raises(HerdrPayloadRejectedError, match="status"):
            await self.host(launcher).server_state()

    async def test_the_command_failing_with_a_message_says_so_instead_of_reading_a_state(self) -> None:
        launcher = RecordingLauncher({STATUS: OutcomeMother.failed("boom", exit_code=2)})

        with pytest.raises(HerdrFailedError, match="boom"):
            await self.host(launcher).server_state()


class TestTheServerIsStartedWithoutALimit(WithAHost):
    async def test_the_server_goes_to_the_unbounded_port_and_never_through_the_launcher(self) -> None:
        launcher = RecordingLauncher()
        unbounded = RecordingUnboundedProcesses()

        await self.host(launcher, unbounded).started_server()

        assert unbounded.detached == [("herdr", "server")]
        assert launcher.calls == []


class TestTheWorkspaces(WithAHost):
    async def test_the_workspaces_with_a_label_are_the_ones_the_list_names_with_it(self) -> None:
        listing = HerdrMother.workspace_list({"w1": "clone", "w2": "other", "w3": "clone"})
        launcher = RecordingLauncher({("herdr", "workspace", "list"): listing})

        assert await self.host(launcher).workspaces_labelled("clone") == ("w1", "w3")

    async def test_the_cwds_are_those_of_the_panes_of_that_workspace(self) -> None:
        panes = HerdrMother.pane_list(["/work/clone", "/elsewhere"])
        launcher = RecordingLauncher({("herdr", "pane", "list", "--workspace", "w4"): panes})

        assert await self.host(launcher).pane_cwds_of("w4") == (Path("/work/clone"), Path("/elsewhere"))

    async def test_a_workspace_list_that_is_not_json_is_rejected(self) -> None:
        launcher = RecordingLauncher({("herdr", "workspace", "list"): OutcomeMother.succeeded("not json")})

        with pytest.raises(HerdrPayloadRejectedError):
            await self.host(launcher).workspaces_labelled("clone")


class TestTheCreationCommands(WithAHost):
    async def test_a_workspace_is_created_in_the_root_with_the_label_and_without_taking_the_focus(self) -> None:
        argv = ("herdr", "workspace", "create", "--cwd", "/work/clone", "--label", "clone", "--no-focus")
        launcher = RecordingLauncher({argv: HerdrMother.workspace_created()})

        created = await self.host(launcher).created_workspace(root=Path("/work/clone"), label="clone")

        assert (created.workspace_id, created.root_pane) == (HerdrMother.WORKSPACE, HerdrMother.PANE)

    async def test_a_creation_answer_without_the_root_pane_is_rejected(self) -> None:
        argv = ("herdr", "workspace", "create", "--cwd", "/work/clone", "--label", "clone", "--no-focus")
        launcher = RecordingLauncher({argv: HerdrMother.workspace_created_without_the_pane()})

        with pytest.raises(HerdrPayloadRejectedError, match="root_pane"):
            await self.host(launcher).created_workspace(root=Path("/work/clone"), label="clone")

    async def test_the_agent_is_started_as_claude_with_its_name_in_the_pane(self) -> None:
        argv = ("herdr", "agent", "start", "coordinador", "--kind", "claude", "--pane", "w1:p3")
        launcher = RecordingLauncher({argv: OutcomeMother.succeeded()})

        await self.host(launcher).started_agent(name="coordinador", pane="w1:p3")

        assert launcher.calls == [argv]

    async def test_a_pane_is_split_to_the_right_and_the_new_pane_is_returned(self) -> None:
        argv = ("herdr", "pane", "split", "w1:p3", "--direction", "right", "--no-focus")
        launcher = RecordingLauncher({argv: HerdrMother.pane_split("w1:p4")})

        assert await self.host(launcher).split_right("w1:p3") == "w1:p4"

    async def test_a_command_is_run_in_a_pane_as_one_quoted_line(self) -> None:
        argv = ("herdr", "pane", "run", "w1:p4", "slice-panel")
        launcher = RecordingLauncher({argv: OutcomeMother.succeeded()})

        await self.host(launcher).ran_in(pane="w1:p4", command=("slice-panel",))

        assert launcher.calls == [argv]

    async def test_a_failing_command_raises_with_what_herdr_said(self) -> None:
        argv = ("herdr", "agent", "start", "coordinador", "--kind", "claude", "--pane", "w1:p3")
        launcher = RecordingLauncher({argv: OutcomeMother.failed("pane not found")})

        with pytest.raises(HerdrFailedError, match="pane not found"):
            await self.host(launcher).started_agent(name="coordinador", pane="w1:p3")

    @pytest.mark.parametrize(
        "answer", [HerdrMother.agent_name_taken_on_stdout(), HerdrMother.agent_name_taken_on_stderr()]
    )
    async def test_a_name_herdr_says_is_taken_is_told_apart_from_any_other_failure(
        self, answer: ProcessOutcome
    ) -> None:
        argv = ("herdr", "agent", "start", "coordinador-clone", "--kind", "claude", "--pane", "w1:p3")
        launcher = RecordingLauncher({argv: answer})

        with pytest.raises(AgentNameTakenError, match="coordinador-clone"):
            await self.host(launcher).started_agent(name="coordinador-clone", pane="w1:p3")

    async def test_any_other_herdr_error_while_starting_the_agent_stays_a_plain_herdr_failure(self) -> None:
        argv = ("herdr", "agent", "start", "coordinador-clone", "--kind", "claude", "--pane", "w1:p3")
        launcher = RecordingLauncher({argv: HerdrMother.other_herdr_error()})

        with pytest.raises(HerdrFailedError, match="pane_not_found"):
            await self.host(launcher).started_agent(name="coordinador-clone", pane="w1:p3")

    async def test_a_command_that_times_out_is_not_swallowed(self) -> None:
        argv = ("herdr", "workspace", "focus", "w1")
        launcher = RecordingLauncher({argv: ProcessTimedOutError(argv, 60.0)})

        with pytest.raises(ProcessTimedOutError):
            await self.host(launcher).focused("w1")


class TestTheWorkspaceIsClosedById(WithAHost):
    async def test_the_workspace_is_closed_with_the_close_command(self) -> None:
        argv = ("herdr", "workspace", "close", "w1")
        launcher = RecordingLauncher({argv: OutcomeMother.succeeded()})

        await self.host(launcher).closed_workspace("w1")

        assert launcher.calls == [argv]

    async def test_a_failing_close_raises_with_what_herdr_said(self) -> None:
        argv = ("herdr", "workspace", "close", "w1")
        launcher = RecordingLauncher({argv: OutcomeMother.failed("workspace not found")})

        with pytest.raises(HerdrFailedError, match="workspace not found"):
            await self.host(launcher).closed_workspace("w1")


class TestTheFocusAndTheAttach(WithAHost):
    async def test_the_workspace_is_focused_through_the_launcher_with_its_limit(self) -> None:
        argv = ("herdr", "workspace", "focus", "w1")
        launcher = RecordingLauncher({argv: OutcomeMother.succeeded()})

        await self.host(launcher).focused("w1")

        assert launcher.calls == [argv]

    async def test_the_attach_replaces_the_process_through_the_unbounded_port_and_never_through_the_launcher(
        self,
    ) -> None:
        launcher = RecordingLauncher()
        unbounded = RecordingUnboundedProcesses()

        with pytest.raises(AttachedToTheSessionError):
            await self.host(launcher, unbounded).attached()

        assert unbounded.replacements == [("herdr",)]
        assert launcher.calls == []
