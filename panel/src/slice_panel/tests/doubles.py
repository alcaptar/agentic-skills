from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, NoReturn

from slice_panel.domain.clock import Clock
from slice_panel.domain.created_workspace import CreatedWorkspace
from slice_panel.domain.exceptions import AgentNameTakenError
from slice_panel.domain.follow_source import FollowSource
from slice_panel.domain.process_launcher import ProcessLauncher
from slice_panel.domain.run_tabs import RunTabs
from slice_panel.domain.server_state import ServerState
from slice_panel.domain.tab_handle import TabHandle
from slice_panel.domain.workspace_host import WorkspaceHost
from slice_panel.infrastructure.unbounded_processes import UnboundedProcesses

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping, Sequence
    from pathlib import Path

    from slice_panel.domain.follow_ended import FollowEnded
    from slice_panel.domain.follow_line import FollowLine
    from slice_panel.domain.process_outcome import ProcessOutcome


class ScriptedFollowSource(FollowSource):
    def __init__(self, *, lines: Sequence[FollowLine], ended: FollowEnded | None = None) -> None:
        self._lines = lines
        self._ended = ended

    async def events(self) -> AsyncIterator[FollowLine | FollowEnded]:
        for line in self._lines:
            yield line
        if self._ended is not None:
            yield self._ended


class RecordingLauncher(ProcessLauncher):
    def __init__(self, answers: Mapping[tuple[str, ...], ProcessOutcome | BaseException] | None = None) -> None:
        self._answers = dict(answers or {})
        self.calls: list[tuple[str, ...]] = []

    async def ran(self, argv: Sequence[str], *, cwd: Path | None = None) -> ProcessOutcome:
        key = tuple(argv)
        self.calls.append(key)
        if key not in self._answers:
            raise AssertionError(f"nobody wrote an answer for {key}")
        answer = self._answers[key]
        if isinstance(answer, BaseException):
            raise answer

        return answer

    def calls_to(self, *prefix: str) -> list[tuple[str, ...]]:
        return [call for call in self.calls if call[: len(prefix)] == prefix]


class RecordingTabs(RunTabs):
    HANDLE: ClassVar[TabHandle] = TabHandle(tab_id="w1:t9")

    def __init__(self) -> None:
        self.opened_runs: list[tuple[str, int, str, Path]] = []
        self.focused_tabs: list[TabHandle] = []

    async def opened_run_of(self, *, repo: str, parent: int, slice_id: str, cwd: Path) -> TabHandle:
        self.opened_runs.append((repo, parent, slice_id, cwd))

        return self.HANDLE

    async def focused(self, handle: TabHandle) -> None:
        self.focused_tabs.append(handle)


class AttachedToTheSessionError(Exception):
    pass


class FakeClock(Clock):
    def __init__(self) -> None:
        self._now = 0.0
        self.slept: list[float] = []

    def now(self) -> float:
        return self._now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self._now += seconds


class RecordingWorkspaceHost(WorkspaceHost):
    CREATED: ClassVar[CreatedWorkspace] = CreatedWorkspace(workspace_id="w9", root_pane="w9:p1")
    SPLIT_PANE: ClassVar[str] = "w9:p2"

    def __init__(
        self,
        *,
        server_states: Sequence[ServerState] = (ServerState.RUNNING,),
        workspaces: Mapping[str, Sequence[str]] | None = None,
        pane_cwds: Mapping[str, Sequence[Path]] | None = None,
        taken_agent_names: Sequence[str] = (),
        failures: Mapping[str, BaseException] | None = None,
    ) -> None:
        self._server_states = server_states
        self._workspaces = workspaces or {}
        self._pane_cwds = pane_cwds or {}
        self._agent_names = set(taken_agent_names)
        self._failures = failures or {}
        self._asked_state = 0
        self.events: list[tuple[object, ...]] = []

    async def server_state(self) -> ServerState:
        self.events.append(("server_state",))
        answer = self._server_states[min(self._asked_state, len(self._server_states) - 1)]
        self._asked_state += 1

        return answer

    async def started_server(self) -> None:
        self.events.append(("started_server",))

    async def workspaces_labelled(self, label: str) -> tuple[str, ...]:
        self.events.append(("workspaces_labelled", label))

        return tuple(self._workspaces.get(label, ()))

    async def pane_cwds_of(self, workspace: str) -> tuple[Path, ...]:
        self.events.append(("pane_cwds_of", workspace))

        return tuple(self._pane_cwds.get(workspace, ()))

    async def created_workspace(self, *, root: Path, label: str) -> CreatedWorkspace:
        self.events.append(("created_workspace", root, label))

        return self.CREATED

    async def started_agent(self, *, name: str, pane: str) -> None:
        self.events.append(("started_agent", name, pane))
        self._fail_if_asked("started_agent")
        if name in self._agent_names:
            raise AgentNameTakenError(name)
        self._agent_names.add(name)

    async def split_right(self, pane: str) -> str:
        self.events.append(("split_right", pane))
        self._fail_if_asked("split_right")

        return self.SPLIT_PANE

    async def ran_in(self, *, pane: str, command: Sequence[str]) -> None:
        self.events.append(("ran_in", pane, tuple(command)))
        self._fail_if_asked("ran_in")

    async def focused(self, workspace: str) -> None:
        self.events.append(("focused", workspace))
        self._fail_if_asked("focused")

    async def closed_workspace(self, workspace: str) -> None:
        self.events.append(("closed_workspace", workspace))
        self._fail_if_asked("closed_workspace")

    async def attached(self) -> NoReturn:
        self.events.append(("attached",))
        raise AttachedToTheSessionError

    def _fail_if_asked(self, operation: str) -> None:
        if operation in self._failures:
            raise self._failures[operation]


class RecordingUnboundedProcesses(UnboundedProcesses):
    def __init__(self) -> None:
        self.detached: list[tuple[str, ...]] = []
        self.replacements: list[tuple[str, ...]] = []

    def spawned_detached(self, argv: Sequence[str]) -> None:
        self.detached.append(tuple(argv))

    def replaced_by(self, argv: Sequence[str]) -> NoReturn:
        self.replacements.append(tuple(argv))
        raise AttachedToTheSessionError
