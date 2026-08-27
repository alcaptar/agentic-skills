from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from slice_runner.domain.event import Event
from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.step import Step
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother


class EventMother:
    REPO: ClassVar[str] = "alcaptar/agentic-skills"
    ISSUE: ClassVar[int] = 150

    @classmethod
    def advancing(cls) -> Event:
        return Event(
            slice_id="slice-05",
            repo=cls.REPO,
            issue=cls.ISSUE,
            step=Step.RUN_CONTROLS,
            at=datetime(2024, 1, 1, 12, 30, 45, tzinfo=UTC),
            spend=HarnessSpendMother.of_the_implementer_call(),
            status=EventStatus.ADVANCING,
        )

    @classmethod
    def closed(cls) -> Event:
        return Event(
            slice_id="slice-05",
            repo=cls.REPO,
            issue=cls.ISSUE,
            step=Step.AWAIT_MERGE,
            at=datetime(2024, 1, 1, 12, 31, 15, tzinfo=UTC),
            spend=HarnessSpendMother.of_the_judge_call(),
            status=EventStatus.CLOSED,
        )
