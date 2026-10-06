from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.widgets import Static, Tree

from slice_panel.domain.follow_ended import FollowEnded
from slice_panel.infrastructure.panel_app import PanelApp
from slice_panel.infrastructure.slice_runner_commands import SliceRunnerCommands
from slice_panel.tests.doubles import RecordingLauncher, ScriptedFollowSource
from slice_panel.tests.mothers.follow_line_mother import FollowLineMother
from slice_panel.tests.mothers.status_output_mother import StatusOutputMother

if TYPE_CHECKING:
    from collections.abc import Sequence

    from textual.pilot import Pilot

    from slice_panel.domain.follow_line import FollowLine


CLONE_ROOT = Path("/work/clone")


class OnScreen:
    @staticmethod
    async def settled(pilot: Pilot[None]) -> None:
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()

    @staticmethod
    def source_of(lines: Sequence[FollowLine], ended: FollowEnded | None = None) -> ScriptedFollowSource:
        return ScriptedFollowSource(lines=lines, ended=ended)

    @staticmethod
    def launcher_that_knows_the_waiting_slice() -> RecordingLauncher:
        waiting = FollowLineMother.awaiting_person()
        argv = SliceRunnerCommands.understanding(repo=waiting.repo, issue=waiting.issue)

        return RecordingLauncher({argv: StatusOutputMother.a_long_understanding()})

    @classmethod
    def panel(
        cls,
        lines: Sequence[FollowLine],
        ended: FollowEnded | None = None,
        launcher: RecordingLauncher | None = None,
    ) -> PanelApp:
        return PanelApp(
            source=cls.source_of(lines, ended),
            launcher=launcher or cls.launcher_that_knows_the_waiting_slice(),
            clone_root=CLONE_ROOT,
            repo=FollowLineMother.REPO,
        )

    @staticmethod
    def tree_lines(pilot: Pilot[None]) -> list[str]:
        tree = pilot.app.query_one("#features", Tree)
        lines: list[str] = []
        pending = list(reversed(tree.root.children))
        while pending:
            node = pending.pop()
            lines.append(f"{'' if node.children else '  '}{node.label!s}")
            pending.extend(reversed(node.children))

        return lines

    @staticmethod
    def detail(pilot: Pilot[None]) -> str:
        return str(pilot.app.query_one("#detail", Static).content)

    @staticmethod
    def notice(pilot: Pilot[None]) -> str:
        return str(pilot.app.query_one("#notice", Static).content)


class TestTheFeaturesOnTheLeft(OnScreen):
    async def test_the_slices_are_grouped_under_the_parent_of_their_line(self) -> None:
        lines = [
            FollowLineMother.advancing(),
            FollowLineMother.of_another_feature(),
            FollowLineMother.awaiting_person(),
        ]
        async with self.panel(lines).run_test() as pilot:
            await self.settled(pilot)

            shown = self.tree_lines(pilot)

        assert [line.strip() for line in shown if line.startswith("feature")] == ["feature 140", "feature 200"]
        assert shown.index("feature 140") < shown.index("feature 200")

    async def test_the_lines_without_a_parent_get_a_group_of_their_own(self) -> None:
        lines = [FollowLineMother.advancing_without_the_feature()]
        async with self.panel(lines).run_test() as pilot:
            await self.settled(pilot)

            shown = self.tree_lines(pilot)

        assert shown[0] == "no feature"
        assert "slice-05" in shown[1]

    async def test_a_slice_keeps_its_last_known_parent_when_a_later_line_comes_without_one(self) -> None:
        lines = [FollowLineMother.advancing(), FollowLineMother.advancing_without_the_feature()]
        async with self.panel(lines).run_test() as pilot:
            await self.settled(pilot)

            shown = self.tree_lines(pilot)

        assert shown[0] == "feature 140"
        assert "no feature" not in shown
        assert "follow-speaks-json" in shown[1]

    async def test_a_slice_shows_the_status_of_its_latest_line_whatever_the_order_they_arrive_in(self) -> None:
        lines = [FollowLineMother.closed(), FollowLineMother.advancing()]
        async with self.panel(lines).run_test() as pilot:
            await self.settled(pilot)

            shown = self.tree_lines(pilot)

        assert shown[1].endswith("closed")


class TestTheSlicesThatWaitForAPerson(OnScreen):
    async def test_only_the_slice_whose_last_status_is_awaiting_person_is_marked_as_waiting_for_you(self) -> None:
        lines = [
            FollowLineMother.advancing(),
            FollowLineMother.awaiting_person(),
            FollowLineMother.waiting_for_a_machine(),
        ]
        async with self.panel(lines).run_test() as pilot:
            await self.settled(pilot)

            shown = self.tree_lines(pilot)

        marked = [line for line in shown if "waits for you" in line]
        assert len(marked) == 1
        assert "slice-06" in marked[0]

    async def test_a_slice_that_stopped_waiting_for_a_person_loses_the_mark(self) -> None:
        lines = [FollowLineMother.awaiting_person(), FollowLineMother.after_the_person_answered()]
        async with self.panel(lines).run_test() as pilot:
            await self.settled(pilot)

            shown = self.tree_lines(pilot)

        assert not any("waits for you" in line for line in shown)


class TestTheDetailOnTheRight(OnScreen):
    async def test_the_selected_slice_shows_its_status_step_spend_and_latest_events(self) -> None:
        lines = [FollowLineMother.advancing(), FollowLineMother.closed()]
        async with self.panel(lines).run_test() as pilot:
            await self.settled(pilot)

            detail = self.detail(pilot)

        assert "slice-05" in detail
        assert "closed" in detail
        assert "await-merge" in detail
        assert "$0.05" in detail
        assert "run-controls" in detail
        assert detail.index("await-merge") < detail.rindex("run-controls")

    async def test_moving_the_cursor_to_another_slice_shows_the_detail_of_that_one(self) -> None:
        lines = [FollowLineMother.advancing(), FollowLineMother.awaiting_person()]
        async with self.panel(lines).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("down")
            await pilot.pause()

            detail = self.detail(pilot)

        assert "slice-06" in detail
        assert "understand" in detail

    async def test_a_status_the_panel_does_not_know_is_shown_as_it_arrived(self) -> None:
        lines = [FollowLineMother.with_a_status_the_panel_does_not_know()]
        async with self.panel(lines).run_test() as pilot:
            await self.settled(pilot)

            detail = self.detail(pilot)

        assert "teleporting" in detail


class TestWhenFollowEnds(OnScreen):
    async def test_the_panel_says_on_screen_that_follow_ended_and_why(self) -> None:
        ended = FollowEnded(exit_code=3, detail="gh is not authenticated")
        async with self.panel([FollowLineMother.advancing()], ended).run_test() as pilot:
            await self.settled(pilot)

            notice = self.notice(pilot)

        assert "follow ended" in notice
        assert "exit 3" in notice
        assert "gh is not authenticated" in notice

    async def test_the_notice_stays_empty_while_follow_is_still_running(self) -> None:
        async with self.panel([FollowLineMother.advancing()]).run_test() as pilot:
            await self.settled(pilot)

            notice = self.notice(pilot)

        assert notice == ""
