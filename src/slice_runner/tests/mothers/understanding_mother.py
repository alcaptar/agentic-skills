from __future__ import annotations

from slice_runner.domain.understanding import Understanding
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother


class UnderstandingMother:
    TEXT = "## Entendimiento de la slice\n\nslice-05 (prechecks-deterministas)\n"

    @classmethod
    def of_the_chosen_slice(cls) -> Understanding:
        return Understanding(text=cls.TEXT, spend=HarnessSpendMother.of_the_understanding_call())
