from __future__ import annotations

from slice_runner.domain.call_spend_log import HarnessCallSpend
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother


class HarnessCallSpendMother:
    @classmethod
    def of_the_implementer(cls) -> HarnessCallSpend:
        return HarnessCallSpend(
            session=HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER, spend=HarnessSpendMother.of_the_implementer_call()
        )

    @classmethod
    def of_the_judge(cls) -> HarnessCallSpend:
        return HarnessCallSpend(
            session=HarnessEnvelopeMother.SESSION_OF_THE_JUDGE, spend=HarnessSpendMother.of_the_judge_call()
        )
