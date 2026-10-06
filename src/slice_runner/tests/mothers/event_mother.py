from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from slice_runner.domain.event import Event
from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother


class EventMother:
    REPO: ClassVar[str] = "alcaptar/agentic-skills"
    ISSUE: ClassVar[int] = 150
    ANOTHER_REPO: ClassVar[str] = "alcaptar/another-repo"

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
            closed_as=None,
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
            closed_as=RunState.MERGED,
        )

    @classmethod
    def blocked_by_the_judge(cls) -> Event:
        return replace(cls.closed(), closed_as=RunState.BLOCKED_VERIFY)

    @classmethod
    def closed_before_the_closing_state_was_recorded(cls) -> Event:
        return replace(cls.closed(), closed_as=None)

    @classmethod
    def advancing_again(cls, *, minutes_later: int) -> Event:
        event = cls.advancing()

        return replace(event, at=event.at + timedelta(minutes=minutes_later))

    @classmethod
    def advancing_in_another_slice(cls) -> Event:
        return replace(cls.advancing(), slice_id="slice-06")

    @classmethod
    def advancing_in_another_repo(cls) -> Event:
        return replace(cls.advancing(), repo=cls.ANOTHER_REPO)

    @classmethod
    def waiting_on_a_machine(cls) -> Event:
        return replace(cls.advancing_again(minutes_later=1), step=Step.AWAIT_CI, status=EventStatus.WAITING)
