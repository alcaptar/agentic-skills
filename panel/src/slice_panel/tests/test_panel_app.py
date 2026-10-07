from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding
from textual.widgets import Footer, Static, Tree
from textual.widgets._footer import FooterKey

from slice_panel.domain.follow_ended import FollowEnded
from slice_panel.infrastructure.panel_app import PanelApp
from slice_panel.infrastructure.slice_runner_commands import SliceRunnerCommands
from slice_panel.tests.doubles import RecordingLauncher, ScriptedFollowSource
from slice_panel.tests.mothers.follow_line_mother import FollowLineMother
from slice_panel.tests.mothers.herdr_mother import HerdrMother
from slice_panel.tests.mothers.outcome_mother import OutcomeMother
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
            workspace=HerdrMother.WORKSPACE,
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

        assert shown == [
            "feature 140",
            "  #150 slice-05 follow-speaks-json  advancing",
            "  #151 slice-06 the-panel  awaiting-person  <- waits for you",
            "feature 200",
            "  #210 slice-01 another-feature-slice  advancing",
        ]

    async def test_the_lines_without_a_parent_get_a_group_of_their_own(self) -> None:
        lines = [FollowLineMother.advancing_without_the_feature()]
        async with self.panel(lines).run_test() as pilot:
            await self.settled(pilot)

            shown = self.tree_lines(pilot)

        assert shown == ["no feature", "  #150 slice-05  advancing"]

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

    async def test_a_slice_that_status_says_is_closed_shows_as_closed_whatever_the_last_event_of_follow_says(
        self,
    ) -> None:
        listing = SliceRunnerCommands.status(repo=FollowLineMother.REPO, parent=FollowLineMother.PARENT)
        launcher = RecordingLauncher(
            {listing: StatusOutputMother.of_a_slice_merged_by_hand_while_follow_still_says_advancing()}
        )
        async with self.panel([FollowLineMother.advancing()], launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("a")
            await pilot.press(*"140", "enter")
            await self.settled(pilot)

            shown = self.tree_lines(pilot)
            detail = self.detail(pilot)

        assert shown == ["feature 140", "  #150 slice-05 follow-speaks-json  closed"]
        assert "status: closed" in detail

    async def test_a_slice_that_status_says_is_closed_does_not_wait_for_you_even_if_follow_says_it_awaits_a_person(
        self,
    ) -> None:
        awaiting = FollowLineMother.awaiting_person()
        listing = SliceRunnerCommands.status(repo=awaiting.repo, parent=FollowLineMother.PARENT)
        closed_row = StatusOutputMother.row("slice-06", "the-panel", awaiting.issue, label=None, closed=True)
        understanding = SliceRunnerCommands.understanding(repo=awaiting.repo, issue=awaiting.issue)
        launcher = RecordingLauncher(
            {
                listing: OutcomeMother.succeeded(closed_row + "\n"),
                understanding: StatusOutputMother.a_long_understanding(),
            }
        )
        async with self.panel([awaiting], launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("a")
            await pilot.press(*"140", "enter")
            await self.settled(pilot)

            shown = self.tree_lines(pilot)

        assert shown == ["feature 140", "  #151 slice-06 the-panel  closed"]


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


class TestTheScreenFitsATallTree(OnScreen):
    SIZE: ClassVar[tuple[int, int]] = (120, 20)
    LINES: ClassVar[int] = 60

    async def test_the_footer_and_the_notice_stay_inside_the_screen_when_the_tree_is_taller_than_it(self) -> None:
        ended = FollowEnded(exit_code=3, detail="gh is not authenticated")
        lines = FollowLineMother.of_many_slices(self.LINES)
        async with self.panel(lines, ended).run_test(size=self.SIZE) as pilot:
            await self.settled(pilot)

            screen = pilot.app.screen.region
            tree = pilot.app.query_one("#features", Tree)
            footer = pilot.app.query_one(Footer)
            notice = pilot.app.query_one("#notice", Static)

            assert tree.virtual_size.height > screen.height
            assert notice.display
            assert screen.contains_region(notice.region)
            assert screen.contains_region(footer.region)
            assert notice.region.bottom <= footer.region.y

    async def test_an_order_that_cannot_be_given_says_why_inside_the_screen_with_a_tall_tree(self) -> None:
        lines = FollowLineMother.of_many_slices(self.LINES)
        async with self.panel(lines, launcher=RecordingLauncher()).run_test(size=self.SIZE) as pilot:
            await self.settled(pilot)
            await pilot.press("e")
            await self.settled(pilot)

            screen = pilot.app.screen.region
            notice = pilot.app.query_one("#notice", Static)

            assert "no understanding has been read" in self.notice(pilot)
            assert screen.contains_region(notice.region)

    async def test_the_footer_teaches_every_binding_with_its_description(self) -> None:
        async with self.panel([FollowLineMother.advancing()]).run_test(size=self.SIZE) as pilot:
            await self.settled(pilot)

            taught = {(each.key, each.description) for each in pilot.app.query(FooterKey)}

        declared = {(each.key, each.description) for each in Binding.make_bindings(PanelApp.BINDINGS)}

        assert declared <= taught
