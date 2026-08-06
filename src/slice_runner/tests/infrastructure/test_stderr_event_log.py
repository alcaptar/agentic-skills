from __future__ import annotations

import json
from typing import TYPE_CHECKING

from slice_runner.infrastructure.stderr_event_log import StderrEventLog
from slice_runner.tests.mothers.event_mother import EventMother

if TYPE_CHECKING:
    import pytest


class TestStderrEventLog:
    def test_the_event_reaches_standard_error_as_the_contract_payload_and_never_standard_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        StderrEventLog().emit(EventMother.advancing())

        output = capsys.readouterr()
        assert output.out == ""
        assert json.loads(output.err) == {
            "slice_id": "slice-05",
            "step": "run-controls",
            "at": "2024-01-01T12:30:45Z",
            "spend": {"cost_usd": 0.3433209, "turns": 9, "duration_ms": 36315, "calls": 1},
            "status": "advancing",
        }

    def test_two_consecutive_events_land_on_two_separable_lines_and_never_on_a_single_run_together(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = StderrEventLog()

        log.emit(EventMother.advancing())
        log.emit(EventMother.closed())

        payloads = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
        assert [(payload["step"], payload["status"]) for payload in payloads] == [
            ("run-controls", "advancing"),
            ("await-merge", "closed"),
        ]
