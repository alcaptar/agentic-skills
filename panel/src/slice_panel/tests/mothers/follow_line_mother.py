from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import ClassVar

from slice_panel.domain.follow_line import FollowLine


class FollowLineMother:
    REPO: ClassVar[str] = "alcaptar/agentic-skills"
    PARENT: ClassVar[int] = 140
    ANOTHER_PARENT: ClassVar[int] = 200

    @classmethod
    def advancing(cls) -> FollowLine:
        return FollowLine(
            ts=datetime(2024, 1, 1, 12, 30, 45, tzinfo=UTC),
            repo=cls.REPO,
            issue=150,
            slice_id="slice-05",
            step="run-controls",
            status="advancing",
            cost_usd=0.3433209,
            parent=cls.PARENT,
            name="follow-speaks-json",
        )

    @classmethod
    def closed(cls) -> FollowLine:
        return replace(
            cls.advancing(),
            ts=datetime(2024, 1, 1, 12, 31, 15, tzinfo=UTC),
            step="await-merge",
            status="closed",
            cost_usd=0.0512,
        )

    @classmethod
    def advancing_without_the_feature(cls) -> FollowLine:
        return replace(cls.advancing(), ts=datetime(2024, 1, 1, 12, 32, 0, tzinfo=UTC), parent=None, name=None)

    @classmethod
    def awaiting_person(cls) -> FollowLine:
        return replace(
            cls.advancing(),
            ts=datetime(2024, 1, 1, 12, 33, 0, tzinfo=UTC),
            issue=151,
            slice_id="slice-06",
            step="understand",
            status="awaiting-person",
            name="the-panel",
        )

    @classmethod
    def after_the_person_answered(cls) -> FollowLine:
        return replace(
            cls.awaiting_person(),
            ts=datetime(2024, 1, 1, 12, 40, 0, tzinfo=UTC),
            step="implement",
            status="advancing",
        )

    @classmethod
    def waiting_for_a_machine(cls) -> FollowLine:
        return replace(
            cls.advancing(),
            ts=datetime(2024, 1, 1, 12, 34, 0, tzinfo=UTC),
            issue=152,
            slice_id="slice-07",
            step="await-ci",
            status="waiting",
            name="the-keys",
        )

    @classmethod
    def of_another_feature(cls) -> FollowLine:
        return replace(
            cls.advancing(),
            ts=datetime(2024, 1, 1, 12, 35, 0, tzinfo=UTC),
            issue=210,
            slice_id="slice-01",
            parent=cls.ANOTHER_PARENT,
            name="another-feature-slice",
        )

    @classmethod
    def of_many_slices(cls, count: int) -> list[FollowLine]:
        return [
            replace(cls.advancing(), issue=1000 + number, slice_id=f"slice-{number:02d}", name=f"slice-number-{number}")
            for number in range(count)
        ]

    @classmethod
    def with_a_status_the_panel_does_not_know(cls) -> FollowLine:
        return replace(cls.advancing(), status="teleporting")
