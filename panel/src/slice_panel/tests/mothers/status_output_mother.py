from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_panel.tests.mothers.outcome_mother import OutcomeMother

if TYPE_CHECKING:
    from slice_panel.infrastructure.process_outcome import ProcessOutcome


class StatusOutputMother:
    PARENT: ClassVar[int] = 140
    AWAITING_ISSUE: ClassVar[int] = 301
    UNDERSTANDING_LINES: ClassVar[int] = 30

    @staticmethod
    def row(slice_id: str, name: str, issue: int, *, label: str | None, closed: bool = False) -> str:
        body: dict[str, object] = {"version": 1, "slice_id": slice_id, "name": name, "issue": issue, "closed": closed}
        if label is not None:
            body["label"] = label

        return json.dumps(body)

    @classmethod
    def of_a_feature_with_slices_that_never_ran(cls) -> ProcessOutcome:
        rows = [
            cls.row("slice-01", "waits-for-you", cls.AWAITING_ISSUE, label="estado:esperando-alineacion"),
            cls.row("slice-02", "never-ran", 302, label="estado:pendiente"),
            cls.row("slice-03", "already-merged", 303, label=None, closed=True),
        ]

        return OutcomeMother.succeeded("\n".join(rows) + "\n")

    @classmethod
    def a_long_understanding(cls) -> ProcessOutcome:
        text = "\n".join(f"understanding line {number}" for number in range(1, cls.UNDERSTANDING_LINES + 1))

        return OutcomeMother.succeeded(json.dumps({"version": 1, "text": text}))

    @classmethod
    def last_line_of_the_understanding(cls) -> str:
        return f"understanding line {cls.UNDERSTANDING_LINES}"
