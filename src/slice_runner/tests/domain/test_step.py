from __future__ import annotations

import pytest

from slice_runner.domain.step import Step


class TestStepAfterDelivery:
    @pytest.mark.parametrize("step", [Step.AWAIT_CI, Step.AWAIT_MERGE])
    def test_the_steps_that_only_read_the_integration_or_the_pull_request_come_after_delivery(self, step: Step) -> None:
        assert step.is_after_delivery() is True

    @pytest.mark.parametrize("step", [step for step in Step if step not in (Step.AWAIT_CI, Step.AWAIT_MERGE)])
    def test_every_other_step_comes_before_delivery(self, step: Step) -> None:
        assert step.is_after_delivery() is False
