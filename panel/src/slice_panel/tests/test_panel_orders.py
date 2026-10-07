from __future__ import annotations

import shlex
from typing import TYPE_CHECKING, ClassVar

from slice_panel.infrastructure.process_launcher import ProcessTimedOutError
from slice_panel.infrastructure.understanding_screen import UnderstandingScreen
from slice_panel.tests.doubles import RecordingLauncher
from slice_panel.tests.mothers.follow_line_mother import FollowLineMother
from slice_panel.tests.mothers.herdr_mother import HerdrMother
from slice_panel.tests.mothers.outcome_mother import OutcomeMother
from slice_panel.tests.mothers.status_output_mother import StatusOutputMother
from slice_panel.tests.test_panel_app import CLONE_ROOT, OnScreen

if TYPE_CHECKING:
    from textual.pilot import Pilot

    from slice_panel.domain.follow_line import FollowLine
    from slice_panel.infrastructure.process_outcome import ProcessOutcome

REPO = FollowLineMother.REPO


class Commands:
    RUN_OF_SLICE_05: ClassVar[tuple[str, ...]] = (
        "slice-runner",
        "run",
        "140",
        "--repo",
        REPO,
        "--base",
        "master",
        "--slice",
        "slice-05",
    )
    CREATE_TAB: ClassVar[tuple[str, ...]] = (
        "herdr",
        "tab",
        "create",
        "--cwd",
        str(CLONE_ROOT),
        "--workspace",
        HerdrMother.WORKSPACE,
        "--label",
        "slice-05",
        "--no-focus",
    )
    RUN_IN_TAB: ClassVar[tuple[str, ...]] = ("herdr", "pane", "run", HerdrMother.PANE, shlex.join(RUN_OF_SLICE_05))
    FOCUS_TAB: ClassVar[tuple[str, ...]] = ("herdr", "tab", "focus", HerdrMother.TAB)
    GO: ClassVar[tuple[str, ...]] = ("slice-runner", "go", "--repo", REPO, "150")
    STATUS: ClassVar[tuple[str, ...]] = ("slice-runner", "status", "--repo", REPO, "--json", "140")
    UNDERSTANDING: ClassVar[tuple[str, ...]] = ("slice-runner", "understanding", "--repo", REPO, "--json", "301")

    @staticmethod
    def review(text: str) -> tuple[str, ...]:
        return ("slice-runner", "review", "--repo", REPO, "150", text)

    @staticmethod
    def retry(text: str) -> tuple[str, ...]:
        return ("slice-runner", "retry", "--repo", REPO, "150", text)


class WithAnOrderedSlice(OnScreen):
    LINES: ClassVar[list[FollowLine]] = [FollowLineMother.advancing()]

    @staticmethod
    def launching_answers() -> dict[tuple[str, ...], ProcessOutcome | BaseException]:
        return {
            Commands.CREATE_TAB: HerdrMother.tab_created(),
            Commands.RUN_IN_TAB: OutcomeMother.succeeded(),
            Commands.FOCUS_TAB: OutcomeMother.succeeded(),
        }

    @classmethod
    def launcher_that_accepts(cls, *orders: tuple[str, ...]) -> RecordingLauncher:
        answers = cls.launching_answers()
        answers.update({order: OutcomeMother.succeeded() for order in orders})

        return RecordingLauncher(answers)

    @staticmethod
    async def typed(pilot: Pilot[None], text: str) -> None:
        await pilot.press(*("space" if each == " " else each for each in text))
        await pilot.press("enter")


class TestAnOrderIsOneKey(WithAnOrderedSlice):
    async def test_g_agrees_the_understanding_and_then_launches_the_run_in_a_new_herdr_tab(self) -> None:
        launcher = self.launcher_that_accepts(Commands.GO)
        async with self.panel(self.LINES, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("g")
            await self.settled(pilot)

        assert launcher.calls == [Commands.GO, Commands.CREATE_TAB, Commands.RUN_IN_TAB]

    async def test_r_asks_for_the_correction_and_passes_it_as_one_argument_before_launching(self) -> None:
        launcher = self.launcher_that_accepts(Commands.review("use the existing port"))
        async with self.panel(self.LINES, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("r")
            await self.typed(pilot, "use the existing port")
            await self.settled(pilot)

        assert launcher.calls == [Commands.review("use the existing port"), Commands.CREATE_TAB, Commands.RUN_IN_TAB]

    async def test_t_asks_for_the_instruction_and_passes_it_as_one_argument_before_launching(self) -> None:
        launcher = self.launcher_that_accepts(Commands.retry("start from the port"))
        async with self.panel(self.LINES, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("t")
            await self.typed(pilot, "start from the port")
            await self.settled(pilot)

        assert launcher.calls == [Commands.retry("start from the port"), Commands.CREATE_TAB, Commands.RUN_IN_TAB]

    async def test_an_order_that_fails_shows_what_the_subcommand_said_and_launches_nothing(self) -> None:
        launcher = RecordingLauncher({Commands.GO: OutcomeMother.failed("the slice is not awaiting alignment")})
        async with self.panel(self.LINES, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("g")
            await self.settled(pilot)

            notice = self.notice(pilot)

        assert "the slice is not awaiting alignment" in notice
        assert launcher.calls == [Commands.GO]

    async def test_a_cancelled_prompt_gives_no_order(self) -> None:
        launcher = RecordingLauncher()
        async with self.panel(self.LINES, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("r")
            await pilot.press("escape")
            await self.settled(pilot)

        assert launcher.calls == []


class TestLaunchingARun(WithAnOrderedSlice):
    async def test_l_launches_the_run_of_the_selected_slice_from_the_clone_root_in_a_new_tab(self) -> None:
        launcher = self.launcher_that_accepts()
        async with self.panel(self.LINES, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("l")
            await self.settled(pilot)

        assert launcher.calls == [Commands.CREATE_TAB, Commands.RUN_IN_TAB]

    async def test_enter_goes_to_the_tab_of_a_run_the_panel_launched(self) -> None:
        launcher = self.launcher_that_accepts()
        async with self.panel(self.LINES, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("l")
            await self.settled(pilot)
            await pilot.press("enter")
            await self.settled(pilot)

        assert launcher.calls[-1] == Commands.FOCUS_TAB

    async def test_enter_on_a_run_the_panel_did_not_launch_says_so_and_calls_nothing(self) -> None:
        launcher = RecordingLauncher()
        async with self.panel(self.LINES, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("enter")
            await self.settled(pilot)

            notice = self.notice(pilot)

        assert "slice-05" in notice
        assert "did not launch" in notice
        assert launcher.calls == []

    async def test_a_slice_whose_feature_is_unknown_cannot_be_launched_and_says_so(self) -> None:
        launcher = RecordingLauncher()
        lines = [FollowLineMother.advancing_without_the_feature()]
        async with self.panel(lines, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("l")
            await self.settled(pilot)

            notice = self.notice(pilot)

        assert "feature" in notice
        assert launcher.calls == []

    async def test_a_herdr_answer_without_the_pane_is_reported_and_nothing_runs_in_the_tab(self) -> None:
        launcher = RecordingLauncher({Commands.CREATE_TAB: HerdrMother.tab_created_without_the_pane()})
        async with self.panel(self.LINES, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("l")
            await self.settled(pilot)

            notice = self.notice(pilot)

        assert "herdr" in notice
        assert launcher.calls == [Commands.CREATE_TAB]

    async def test_a_herdr_command_that_fails_shows_what_herdr_said(self) -> None:
        launcher = RecordingLauncher({Commands.CREATE_TAB: OutcomeMother.failed("no herdr server is running")})
        async with self.panel(self.LINES, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("l")
            await self.settled(pilot)

            notice = self.notice(pilot)

        assert "no herdr server is running" in notice


class TestEveryCallHasATimeLimit(WithAnOrderedSlice):
    async def test_an_order_that_runs_out_of_time_says_which_command_and_launches_nothing(self) -> None:
        launcher = RecordingLauncher({Commands.GO: ProcessTimedOutError(Commands.GO, 60.0)})
        async with self.panel(self.LINES, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("g")
            await self.settled(pilot)

            notice = self.notice(pilot)

        assert "slice-runner go" in notice
        assert "did not finish" in notice
        assert launcher.calls == [Commands.GO]

    async def test_a_herdr_call_that_runs_out_of_time_is_reported_the_same_way(self) -> None:
        launcher = RecordingLauncher({Commands.CREATE_TAB: ProcessTimedOutError(Commands.CREATE_TAB, 60.0)})
        async with self.panel(self.LINES, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("l")
            await self.settled(pilot)

            notice = self.notice(pilot)

        assert "herdr tab create" in notice
        assert "did not finish" in notice


class TestAddingAFeature(WithAnOrderedSlice):
    async def test_a_asks_for_the_parent_and_adds_all_its_slices_even_those_that_never_ran_or_are_closed(self) -> None:
        launcher = RecordingLauncher(
            {
                Commands.STATUS: StatusOutputMother.of_a_feature_with_slices_that_never_ran(),
                Commands.UNDERSTANDING: StatusOutputMother.a_long_understanding(),
            }
        )
        async with self.panel([], launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("a")
            await self.typed(pilot, "140")
            await self.settled(pilot)

            shown = self.tree_lines(pilot)

        assert shown[0] == "feature 140"
        assert "slice-01 waits-for-you" in shown[1]
        assert "slice-02 never-ran" in shown[2]
        assert "estado:pendiente" in shown[2]
        assert shown[3].endswith("closed")
        assert launcher.calls_to("slice-runner", "status") == [Commands.STATUS]

    async def test_a_parent_that_is_not_a_number_is_refused_without_calling_anything(self) -> None:
        launcher = RecordingLauncher()
        async with self.panel([], launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("a")
            await self.typed(pilot, "abc")
            await self.settled(pilot)

            notice = self.notice(pilot)

        assert "abc" in notice
        assert launcher.calls == []

    async def test_a_status_that_fails_shows_what_the_subcommand_said(self) -> None:
        launcher = RecordingLauncher({Commands.STATUS: OutcomeMother.failed("issue 140 does not exist")})
        async with self.panel([], launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("a")
            await self.typed(pilot, "140")
            await self.settled(pilot)

            notice = self.notice(pilot)

        assert "issue 140 does not exist" in notice

    async def test_a_status_the_panel_cannot_read_is_reported_instead_of_added_halfway(self) -> None:
        launcher = RecordingLauncher({Commands.STATUS: OutcomeMother.succeeded('{"version": 1, "surprise": true}\n')})
        async with self.panel([], launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("a")
            await self.typed(pilot, "140")
            await self.settled(pilot)

            notice = self.notice(pilot)
            shown = self.tree_lines(pilot)

        assert "status" in notice
        assert shown == []


class TestTheUnderstandingOfASliceThatWaits(WithAnOrderedSlice):
    @staticmethod
    def launcher() -> RecordingLauncher:
        return RecordingLauncher(
            {
                Commands.STATUS: StatusOutputMother.of_a_feature_with_slices_that_never_ran(),
                Commands.UNDERSTANDING: StatusOutputMother.a_long_understanding(),
            }
        )

    async def test_the_detail_shows_the_start_of_the_understanding_and_only_the_start(self) -> None:
        async with self.panel([], launcher=self.launcher()).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("a")
            await self.typed(pilot, "140")
            await self.settled(pilot)

            detail = self.detail(pilot)

        assert "understanding line 1" in detail
        assert StatusOutputMother.last_line_of_the_understanding() not in detail

    async def test_the_understanding_is_read_once_however_many_times_the_screen_refreshes(self) -> None:
        launcher = self.launcher()
        async with self.panel([], launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            for _ in range(3):
                await pilot.press("a")
                await self.typed(pilot, "140")
                await self.settled(pilot)
            await pilot.press("down", "up", "down", "up")
            await self.settled(pilot)

        assert launcher.calls_to("slice-runner", "understanding") == [Commands.UNDERSTANDING]

    async def test_e_opens_the_whole_understanding(self) -> None:
        async with self.panel([], launcher=self.launcher()).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("a")
            await self.typed(pilot, "140")
            await self.settled(pilot)
            await pilot.press("e")
            await self.settled(pilot)

            screen = pilot.app.screen

            assert isinstance(screen, UnderstandingScreen)
            assert StatusOutputMother.last_line_of_the_understanding() in screen.shown_text()

    async def test_a_slice_that_does_not_wait_reads_no_understanding(self) -> None:
        launcher = RecordingLauncher()
        async with self.panel(self.LINES, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("e")
            await self.settled(pilot)

        assert launcher.calls == []

    async def test_a_slice_that_waits_according_to_follow_reads_its_understanding_when_selected(self) -> None:
        argv = ("slice-runner", "understanding", "--repo", REPO, "--json", "151")
        launcher = RecordingLauncher({argv: StatusOutputMother.a_long_understanding()})
        async with self.panel([FollowLineMother.awaiting_person()], launcher=launcher).run_test() as pilot:
            await self.settled(pilot)

            detail = self.detail(pilot)

        assert "understanding line 1" in detail

    async def test_an_understanding_that_cannot_be_read_says_why_and_is_not_asked_again(self) -> None:
        launcher = RecordingLauncher(
            {
                Commands.UNDERSTANDING: OutcomeMother.failed("no understanding published"),
                Commands.STATUS: StatusOutputMother.of_a_feature_with_slices_that_never_ran(),
            }
        )
        async with self.panel([], launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            await pilot.press("a")
            await self.typed(pilot, "140")
            await self.settled(pilot)
            await pilot.press("down", "up")
            await self.settled(pilot)

            notice = self.notice(pilot)

        assert "no understanding published" in notice
        assert launcher.calls_to("slice-runner", "understanding") == [Commands.UNDERSTANDING]


class TestNoCommandMerges(WithAnOrderedSlice):
    async def test_none_of_the_commands_the_panel_invokes_is_a_merge(self) -> None:
        launcher = RecordingLauncher(
            {
                **self.launching_answers(),
                Commands.GO: OutcomeMother.succeeded(),
                Commands.review("x"): OutcomeMother.succeeded(),
                Commands.retry("x"): OutcomeMother.succeeded(),
                Commands.STATUS: StatusOutputMother.of_a_feature_with_slices_that_never_ran(),
                Commands.UNDERSTANDING: StatusOutputMother.a_long_understanding(),
            }
        )
        async with self.panel(self.LINES, launcher=launcher).run_test() as pilot:
            await self.settled(pilot)
            for key in ("g", "l", "enter"):
                await pilot.press(key)
                await self.settled(pilot)
            for key in ("r", "t"):
                await pilot.press(key)
                await self.typed(pilot, "x")
                await self.settled(pilot)
            await pilot.press("a")
            await self.typed(pilot, "140")
            await self.settled(pilot)
            await pilot.press("e", "escape")

        assert len(launcher.calls) >= 8
        assert not any("merge" in part for call in launcher.calls for part in call)
        assert ("gh", "pr", "merge") not in [call[:3] for call in launcher.calls]
