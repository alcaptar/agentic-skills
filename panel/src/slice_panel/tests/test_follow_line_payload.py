from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_panel.infrastructure.follow_line_payload import FollowLinePayload, FollowLineRejectedError
from slice_panel.tests.mothers.follow_line_mother import FollowLineMother

if TYPE_CHECKING:
    from slice_panel.domain.follow_line import FollowLine


class TestTheLineThatFollowPrints:
    @staticmethod
    def _line(**overrides: object) -> str:
        line: dict[str, object] = {
            "version": 1,
            "ts": "2024-01-01T12:30:45+00:00",
            "repo": "alcaptar/agentic-skills",
            "issue": 150,
            "slice_id": "slice-05",
            "step": "run-controls",
            "status": "advancing",
            "cost_usd": 0.3433209,
            "parent": 140,
            "name": "follow-speaks-json",
        }
        line.update(overrides)

        return json.dumps(line)

    def test_a_line_becomes_the_value_object_the_panel_works_with(self) -> None:
        assert FollowLinePayload.parsed(self._line()).to_domain() == FollowLineMother.advancing()

    def test_a_line_with_keys_the_panel_does_not_know_is_read_ignoring_them(self) -> None:
        line = self._line(closed_as="merged", tomorrow_new_key={"nested": [1, 2]})

        assert FollowLinePayload.parsed(line).to_domain() == FollowLineMother.advancing()

    def test_a_line_without_parent_nor_name_leaves_them_empty(self) -> None:
        line = json.loads(self._line())
        del line["parent"]
        del line["name"]

        parsed: FollowLine = FollowLinePayload.parsed(json.dumps(line)).to_domain()

        assert (parsed.parent, parsed.name) == (None, None)

    def test_a_known_key_with_the_wrong_type_is_rejected(self) -> None:
        with pytest.raises(FollowLineRejectedError, match="issue"):
            FollowLinePayload.parsed(self._line(issue="a hundred"))

    def test_a_known_key_that_is_missing_is_rejected(self) -> None:
        line = json.loads(self._line())
        del line["status"]

        with pytest.raises(FollowLineRejectedError, match="status"):
            FollowLinePayload.parsed(json.dumps(line))

    def test_a_line_that_is_not_json_is_corruption_and_is_rejected(self) -> None:
        with pytest.raises(FollowLineRejectedError, match="not JSON"):
            FollowLinePayload.parsed("this is not json")
