from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.infrastructure.system_clock import SystemClock

if TYPE_CHECKING:
    import pytest


class TestSystemClock:
    def test_the_seconds_it_is_asked_to_wait_reach_the_system_call_untouched(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        slept: list[float] = []
        monkeypatch.setattr("time.sleep", slept.append)

        SystemClock().sleep(seconds=30)

        assert slept == [30]
