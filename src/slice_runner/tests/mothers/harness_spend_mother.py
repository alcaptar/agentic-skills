from __future__ import annotations

from slice_runner.domain.harness_spend import HarnessSpend


class HarnessSpendMother:
    @staticmethod
    def of_the_implementer_call() -> HarnessSpend:
        return HarnessSpend.of_a_call(cost_usd=0.3433209, turns=9, duration_ms=36315)

    @staticmethod
    def of_the_judge_call() -> HarnessSpend:
        return HarnessSpend.of_a_call(cost_usd=0.051877, turns=5, duration_ms=29337)

    @staticmethod
    def of_the_understanding_call() -> HarnessSpend:
        return HarnessSpend.of_a_call(cost_usd=0.021415, turns=3, duration_ms=14208)
