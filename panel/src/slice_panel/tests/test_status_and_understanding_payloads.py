from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pytest

from slice_panel.infrastructure.status_line_payload import StatusLinePayload, StatusRejectedError
from slice_panel.infrastructure.understanding_line_payload import UnderstandingLinePayload, UnderstandingRejectedError


class Contract:
    CONTRACTS: ClassVar[Path] = Path(__file__).resolve().parents[4] / "contract"

    @classmethod
    def examples(cls, name: str) -> list[dict[str, object]]:
        examples: list[dict[str, object]] = json.loads((cls.CONTRACTS / name).read_text(encoding="utf-8"))["examples"]

        return examples


class TestTheStatusExamplesOfTheContract(Contract):
    def test_every_example_becomes_a_listing_of_the_feature_it_was_asked_for(self) -> None:
        text = "".join(f"{json.dumps(each)}\n" for each in self.examples("status-line.json"))

        listings = StatusLinePayload.listings_of(text, repo="org/repo", parent=9)

        assert [(each.repo, each.parent, each.issue, each.slice_id) for each in listings] == [
            ("org/repo", 9, 473, "slice-03"),
            ("org/repo", 9, 477, "slice-07"),
        ]
        assert listings[0].label == "estado:esperando-merge"
        assert listings[0].pull_request == 480
        assert listings[1].label is None

    def test_a_key_the_contract_does_not_declare_is_rejected_instead_of_ignored(self) -> None:
        row = {**self.examples("status-line.json")[0], "from_the_future": 1}

        with pytest.raises(StatusRejectedError):
            StatusLinePayload.listings_of(json.dumps(row), repo="org/repo", parent=9)

    def test_a_line_that_is_not_json_is_rejected(self) -> None:
        with pytest.raises(StatusRejectedError):
            StatusLinePayload.listings_of("slice-03 pending", repo="org/repo", parent=9)

    def test_an_issue_number_that_arrives_as_text_is_rejected(self) -> None:
        row = {**self.examples("status-line.json")[0], "issue": "473"}

        with pytest.raises(StatusRejectedError):
            StatusLinePayload.listings_of(json.dumps(row), repo="org/repo", parent=9)


class TestTheUnderstandingExamplesOfTheContract(Contract):
    def test_every_example_gives_back_its_text_whole(self) -> None:
        examples = self.examples("understanding-line.json")
        texts = [UnderstandingLinePayload.parsed(json.dumps(each)).text for each in examples]

        assert texts[1] == "Primera linea.\n\nSegunda linea tras un parrafo."

    def test_a_key_the_contract_does_not_declare_is_rejected(self) -> None:
        row = {**self.examples("understanding-line.json")[0], "from_the_future": 1}

        with pytest.raises(UnderstandingRejectedError):
            UnderstandingLinePayload.parsed(json.dumps(row))

    def test_output_that_is_not_json_is_rejected(self) -> None:
        with pytest.raises(UnderstandingRejectedError):
            UnderstandingLinePayload.parsed("the understanding")
