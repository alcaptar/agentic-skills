from __future__ import annotations

from typing import ClassVar

from slice_runner.domain.step import Step
from slice_runner.infrastructure.call_trace import HarnessCall
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother


class HarnessCallMother:
    SLICE_ID: ClassVar[str] = "slice-11"
    SESSION_OF_THE_IMPLEMENTER: ClassVar[str] = HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER
    SESSION_OF_THE_JUDGE: ClassVar[str] = HarnessEnvelopeMother.SESSION_OF_THE_JUDGE

    @classmethod
    def of_the_implementer(cls) -> HarnessCall:
        return HarnessCall(slice_id=cls.SLICE_ID, step=Step.IMPLEMENT, session=cls.SESSION_OF_THE_IMPLEMENTER)

    @classmethod
    def of_the_judge(cls) -> HarnessCall:
        return HarnessCall(slice_id=cls.SLICE_ID, step=Step.VERIFY, session=cls.SESSION_OF_THE_JUDGE)
