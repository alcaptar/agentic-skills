from __future__ import annotations

from pathlib import Path

import pytest

from slice_panel.application.actions.open_environment import OpenEnvironment, OpenEnvironmentParams
from slice_panel.domain.exceptions import (
    MountingAndCleanupFailedError,
    MountingFailedError,
    ServerDidNotStartError,
)
from slice_panel.domain.mounting_step import MountingStep
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
    async def opened(
        cls, host: RecordingWorkspaceHost, clock: FakeClock | None = None, clone_root: Path = CLONE_ROOT
    ) -> None:
        with pytest.raises(AttachedToTheSessionError):
            await cls.open_environment(host, clock or FakeClock()).execute(OpenEnvironmentParams(clone_root=clone_root))

    @classmethod
    async def failed_to_open(
        cls, host: RecordingWorkspaceHost, expected: type[MountingFailedError] = MountingFailedError
    ) -> MountingFailedError:
        with pytest.raises(expected) as raised:
            await cls.open_environment(host, FakeClock()).execute(OpenEnvironmentParams(clone_root=CLONE_ROOT))

        return raised.value

    @staticmethod
    def started_agent_names(host: RecordingWorkspaceHost) -> list[object]:
        return [event[1] for event in host.events if event[0] == "started_agent"]


class TestTheWorkspaceIsMountedFromScratch(WithAnEnvironment):
    async def test_a_repo_without_a_workspace_gets_one_with_the_coordinator_and_the_panel_side_by_side(self) -> None:
        host = RecordingWorkspaceHost()

        await self.opened(host)

        assert host.events == [
            ("server_state",),
            ("workspaces_labelled", LABEL),
            ("created_workspace", CLONE_ROOT, LABEL),
            ("started_agent", "coordinador-clone", CREATED.root_pane),
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


class TestTheCoordinatorIsNamedAfterTheClone(WithAnEnvironment):
    @pytest.mark.parametrize(
        ("folder", "expected"),
        [
            ("clone", "coordinador-clone"),
            ("My.Repo-Ñandú", "coordinador-my-repo--and-"),
            ("snake_case-ok", "coordinador-snake_case-ok"),
            ("a" * 40, "coordinador-" + "a" * 20),
        ],
    )
    async def test_the_name_is_the_folder_lowercased_with_what_herdr_refuses_replaced_and_cut_to_32(
        self, folder: str, expected: str
    ) -> None:
        host = RecordingWorkspaceHost()

        await self.opened(host, clone_root=Path("/work") / folder)

        assert self.started_agent_names(host) == [expected]
        assert len(expected) <= 32

    async def test_a_name_already_used_by_another_workspace_gets_the_next_free_suffix(self) -> None:
        host = RecordingWorkspaceHost(taken_agent_names=["coordinador-clone"])

        await self.opened(host)

        assert self.started_agent_names(host) == ["coordinador-clone", "coordinador-clone-2"]

    async def test_two_clones_with_the_same_folder_name_do_not_collide(self) -> None:
        host = RecordingWorkspaceHost()

        await self.opened(host, clone_root=Path("/a/clone"))
        await self.opened(host, clone_root=Path("/b/clone"))

        assert self.started_agent_names(host) == ["coordinador-clone", "coordinador-clone", "coordinador-clone-2"]

    async def test_the_base_is_trimmed_so_the_suffix_still_fits_in_32(self) -> None:
        base = "coordinador-" + "a" * 20
        host = RecordingWorkspaceHost(taken_agent_names=[base])

        await self.opened(host, clone_root=Path("/work") / ("a" * 40))

        assert self.started_agent_names(host)[-1] == base[:30] + "-2"

    async def test_with_the_base_and_the_eight_suffixes_taken_it_gives_up_after_nine_attempts_and_cleans_up(
        self,
    ) -> None:
        taken = ["coordinador-clone", *[f"coordinador-clone-{number}" for number in range(2, 10)]]
        host = RecordingWorkspaceHost(taken_agent_names=taken)

        error = await self.failed_to_open(host)

        assert error.step is MountingStep.START_COORDINATOR
        assert len(self.started_agent_names(host)) == 9
        assert ("closed_workspace", CREATED.workspace_id) in host.events
        assert ("attached",) not in host.events


class TestAFailureWhileMountingLeavesNothingBehind(WithAnEnvironment):
    @pytest.mark.parametrize(
        ("operation", "step"),
        [
            ("started_agent", MountingStep.START_COORDINATOR),
            ("split_right", MountingStep.SPLIT_PANE),
            ("ran_in", MountingStep.RUN_PANEL),
            ("focused", MountingStep.FOCUS),
        ],
    )
    async def test_the_workspace_it_created_is_closed_the_step_and_its_reason_are_reported_and_it_never_attaches(
        self, operation: str, step: MountingStep
    ) -> None:
        host = RecordingWorkspaceHost(failures={operation: OSError("herdr failed: boom")})

        error = await self.failed_to_open(host)

        assert error.step is step
        assert step in str(error)
        assert "boom" in str(error)
        assert host.events[-1] == ("closed_workspace", CREATED.workspace_id)
        assert ("attached",) not in host.events

    async def test_when_the_cleanup_fails_too_both_reasons_are_reported(self) -> None:
        host = RecordingWorkspaceHost(
            failures={"split_right": OSError("split boom"), "closed_workspace": OSError("close boom")}
        )

        error = await self.failed_to_open(host, MountingAndCleanupFailedError)

        assert error.step is MountingStep.SPLIT_PANE
        assert "split boom" in str(error)
        assert "close boom" in str(error)
        assert ("attached",) not in host.events

    async def test_a_failing_focus_on_a_reused_workspace_closes_nothing_and_starts_nothing(self) -> None:
        host = RecordingWorkspaceHost(
            workspaces={LABEL: ["w4"]},
            pane_cwds={"w4": [CLONE_ROOT]},
            failures={"focused": OSError("focus boom")},
        )

        error = await self.failed_to_open(host)

        assert error.step is MountingStep.FOCUS
        assert "focus boom" in str(error)
        assert [event[0] for event in host.events if event[0] in ("closed_workspace", "started_agent")] == []
        assert ("attached",) not in host.events
