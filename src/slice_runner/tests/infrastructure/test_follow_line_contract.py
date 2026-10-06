from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

from slice_runner.infrastructure.event_follow_line_payload import EventFollowLinePayload
from slice_runner.tests.mothers.event_mother import EventMother


class TestTheFollowLineAgainstItsExamples:
    _CONTRACT: ClassVar[Path] = Path(__file__).resolve().parents[4] / "contract" / "follow-line.json"

    @classmethod
    def _declared(cls) -> dict[str, object]:
        declared: dict[str, object] = json.loads(cls._CONTRACT.read_text(encoding="utf-8"))

        return declared

    @classmethod
    def _keys_of_the_examples(cls) -> set[str]:
        examples = cls._declared()["examples"]
        assert isinstance(examples, list)

        return {key for example in examples for key in example}

    @classmethod
    def _required(cls) -> set[str]:
        optional = cls._declared()["optional"]
        assert isinstance(optional, list)

        return cls._keys_of_the_examples() - set(optional)

    @staticmethod
    def _emitted() -> list[dict[str, object]]:
        events = (
            EventMother.advancing(),
            EventMother.closed(),
            EventMother.advancing_before_the_feature_was_recorded(),
        )

        return [EventFollowLinePayload.from_domain(event).to_contract() for event in events]

    def test_the_program_never_emits_a_key_the_examples_do_not_have(self) -> None:
        emitted = {key for line in self._emitted() for key in line}

        assert emitted - self._keys_of_the_examples() == set()

    def test_the_program_always_emits_the_keys_the_examples_do_not_mark_as_optional(self) -> None:
        for line in self._emitted():
            assert self._required() - set(line) == set()

    def test_the_optional_keys_are_all_keys_the_examples_carry(self) -> None:
        optional = self._declared()["optional"]
        assert isinstance(optional, list)

        assert set(optional) <= self._keys_of_the_examples()

    def test_the_optional_keys_are_the_ones_the_program_leaves_out_when_it_has_no_value(self) -> None:
        optional = self._declared()["optional"]
        assert isinstance(optional, list)
        left_out = {key for key in self._keys_of_the_examples() for line in self._emitted() if key not in line}

        assert left_out == set(optional)
