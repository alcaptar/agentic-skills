from __future__ import annotations

from pathlib import Path

import pytest

from slice_panel.application.actions.open_environment import OpenEnvironment, OpenEnvironmentParams
from slice_panel.domain.exceptions import ServerDidNotStartError
from slice_panel.domain.server_state import ServerState
from slice_panel.domain.server_wait import ServerWait
from slice_panel.tests.doubles import AttachedToTheSessionError, FakeClock, RecordingWorkspaceHost

CLONE_ROOT = Path("/work/clone")
LABEL = "clone"
CREATED = RecordingWorkspaceHost.CREATED
PANEL_COMMAND = ("slice-panel",)


class WithAnEnvironment:
    @staticmethod
    def open_environment(host: RecordingWorkspaceHost, clock: FakeClock) -> OpenEnvironment:
        return OpenEnvironment(host=host, clock=clock, wait=ServerWait(poll_seconds=0.5, deadline_seconds=10.0))

    @classmethod
    async def opened(cls, host: RecordingWorkspaceHost, clock: FakeClock | None = None) -> None:
        with pytest.raises(AttachedToTheSessionError):
            await cls.open_environment(host, clock or FakeClock()).execute(OpenEnvironmentParams(clone_root=CLONE_ROOT))


class TestTheWorkspaceIsMountedFromScratch(WithAnEnvironment):
    async def test_a_repo_without_a_workspace_gets_one_with_the_coordinator_and_the_panel_side_by_side(self) -> None:
        host = RecordingWorkspaceHost()

        await self.opened(host)

        assert host.events == [
            ("server_state",),
            ("workspaces_labelled", LABEL),
            ("created_workspace", CLONE_ROOT, LABEL),
            ("started_agent", "coordinador", CREATED.root_pane),
            ("split_right", CREATED.root_pane),
            ("ran_in", host.SPLIT_PANE, PANEL_COMMAND),
            ("focused", CREATED.workspace_id),
            ("attached",),
        ]


class TestAnExistingWorkspaceIsReused(WithAnEnvironment):
    async def test_a_workspace_with_the_label_and_a_pane_in_the_root_is_focused_and_nothing_is_created(self) -> None:
        host = RecordingWorkspaceHost(workspaces={LABEL: ["w4"]}, pane_cwds={"w4": [Path("/elsewhere"), CLONE_ROOT]})

        await self.opened(host)

        assert host.events == [
            ("server_state",),
            ("workspaces_labelled", LABEL),
            ("pane_cwds_of", "w4"),
            ("focused", "w4"),
            ("attached",),
        ]

    async def test_a_workspace_with_the_label_but_no_pane_in_the_root_does_not_count_and_a_new_one_is_created(
        self,
    ) -> None:
        host = RecordingWorkspaceHost(workspaces={LABEL: ["w4"]}, pane_cwds={"w4": [Path("/elsewhere")]})

        await self.opened(host)

        assert ("created_workspace", CLONE_ROOT, LABEL) in host.events
        assert ("focused", CREATED.workspace_id) in host.events

    async def test_the_second_workspace_with_the_label_is_the_one_reused_when_only_it_has_the_root(self) -> None:
        host = RecordingWorkspaceHost(
            workspaces={LABEL: ["w4", "w5"]}, pane_cwds={"w4": [Path("/elsewhere")], "w5": [CLONE_ROOT]}
        )

        await self.opened(host)

        assert ("focused", "w5") in host.events
        assert not [event for event in host.events if event[0] == "created_workspace"]


class TestTheServerIsStartedWhenItIsNotRunning(WithAnEnvironment):
    async def test_a_server_that_answers_within_the_deadline_is_polled_every_half_second_and_then_the_flow_goes_on(
        self,
    ) -> None:
        host = RecordingWorkspaceHost(server_states=[ServerState.STOPPED, ServerState.STOPPED, ServerState.RUNNING])
        clock = FakeClock()

        await self.opened(host, clock)

        assert host.events[:4] == [("server_state",), ("started_server",), ("server_state",), ("server_state",)]
        assert ("created_workspace", CLONE_ROOT, LABEL) in host.events
        assert clock.slept == [0.5, 0.5]

    async def test_a_server_that_never_answers_fails_after_the_deadline_and_creates_nothing(self) -> None:
        host = RecordingWorkspaceHost(server_states=[ServerState.STOPPED])
        clock = FakeClock()

        with pytest.raises(ServerDidNotStartError, match="10"):
            await self.open_environment(host, clock).execute(OpenEnvironmentParams(clone_root=CLONE_ROOT))

        assert clock.now() == 10.0
        assert [event[0] for event in host.events if event[0] not in ("server_state", "started_server")] == []
        assert [event for event in host.events if event[0] == "started_server"] == [("started_server",)]

    async def test_a_running_server_is_not_started_again(self) -> None:
        host = RecordingWorkspaceHost()

        await self.opened(host)

        assert ("started_server",) not in host.events
