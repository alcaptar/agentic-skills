from __future__ import annotations

from pathlib import Path

import pytest

from slice_panel.application.actions.give_order import GiveOrder, GiveOrderParams
from slice_panel.application.actions.launch_run import LaunchRun
from slice_panel.domain.exceptions import FeatureUnknownError, OrderRefusedError, ProcessTimedOutError
from slice_panel.tests.doubles import RecordingLauncher, RecordingTabs
from slice_panel.tests.mothers.follow_line_mother import FollowLineMother
from slice_panel.tests.mothers.outcome_mother import OutcomeMother
from slice_panel.tests.mothers.slice_view_mother import SliceViewMother

CLONE_ROOT = Path("/work/clone")
ORDER = ("slice-runner", "go", "--repo", FollowLineMother.REPO, "150")


class WithAnOrder:
    @staticmethod
    def give_order(launcher: RecordingLauncher, tabs: RecordingTabs) -> GiveOrder:
        return GiveOrder(launcher=launcher, launch=LaunchRun(tabs=tabs, clone_root=CLONE_ROOT), clone_root=CLONE_ROOT)


class TestTheRunIsLaunchedOnlyWhenTheOrderSucceeds(WithAnOrder):
    async def test_an_order_that_exits_with_zero_launches_the_run_of_the_slice(self) -> None:
        launcher = RecordingLauncher({ORDER: OutcomeMother.succeeded()})
        tabs = RecordingTabs()

        handle = await self.give_order(launcher, tabs).execute(
            GiveOrderParams(view=SliceViewMother.advancing(), order=ORDER)
        )

        assert launcher.calls == [ORDER]
        assert tabs.opened_runs == [
            (FollowLineMother.REPO, FollowLineMother.PARENT, "slice-05", CLONE_ROOT),
        ]
        assert handle == tabs.HANDLE

    @pytest.mark.parametrize("exit_code", [1, 2, 17])
    async def test_an_order_that_exits_with_another_code_launches_nothing_and_says_what_it_said(
        self, exit_code: int
    ) -> None:
        launcher = RecordingLauncher({ORDER: OutcomeMother.failed("not awaiting alignment", exit_code=exit_code)})
        tabs = RecordingTabs()

        with pytest.raises(OrderRefusedError, match="not awaiting alignment"):
            await self.give_order(launcher, tabs).execute(
                GiveOrderParams(view=SliceViewMother.advancing(), order=ORDER)
            )

        assert tabs.opened_runs == []

    async def test_a_refusal_without_output_names_the_command_and_its_exit_code(self) -> None:
        launcher = RecordingLauncher({ORDER: OutcomeMother.failed("", exit_code=9)})

        with pytest.raises(OrderRefusedError, match=r"slice-runner go .* exited 9"):
            await self.give_order(launcher, RecordingTabs()).execute(
                GiveOrderParams(view=SliceViewMother.advancing(), order=ORDER)
            )

    async def test_an_order_that_runs_out_of_time_launches_nothing_and_the_error_is_not_swallowed(self) -> None:
        launcher = RecordingLauncher({ORDER: ProcessTimedOutError(ORDER, 60.0)})
        tabs = RecordingTabs()

        with pytest.raises(ProcessTimedOutError):
            await self.give_order(launcher, tabs).execute(
                GiveOrderParams(view=SliceViewMother.advancing(), order=ORDER)
            )

        assert tabs.opened_runs == []

    async def test_a_slice_without_a_feature_gets_its_order_given_and_then_cannot_be_launched(self) -> None:
        launcher = RecordingLauncher({ORDER: OutcomeMother.succeeded()})
        tabs = RecordingTabs()

        with pytest.raises(FeatureUnknownError, match="slice-05"):
            await self.give_order(launcher, tabs).execute(
                GiveOrderParams(view=SliceViewMother.without_the_feature(), order=ORDER)
            )

        assert launcher.calls == [ORDER]
        assert tabs.opened_runs == []
