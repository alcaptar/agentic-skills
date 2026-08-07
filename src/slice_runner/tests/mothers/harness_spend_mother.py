from __future__ import annotations

from slice_runner.domain.harness_spend import HarnessSpend


class HarnessSpendMother:
    @staticmethod
    def of_the_implementer_call() -> HarnessSpend:
        return HarnessSpend.of_a_call(
            cost_usd=0.3433209, turns=9, duration_ms=36315, models=("claude-sonnet-5",), cache_read_tokens=241303
        )

    @staticmethod
    def of_the_judge_call() -> HarnessSpend:
        return HarnessSpend.of_a_call(
            cost_usd=0.051877,
            turns=5,
            duration_ms=29337,
            models=("claude-haiku-4-5-20251001",),
            cache_read_tokens=15510,
        )
