from __future__ import annotations

from typing import ClassVar

from slice_runner.domain.call_trace import HarnessCall
from slice_runner.domain.step import Step
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother


class HarnessCallMother:
    REPO: ClassVar[str] = "alcaptar/agentic-skills"
    ISSUE: ClassVar[int] = 11
    OTHER_REPO: ClassVar[str] = "alcaptar/another-feature"
    OTHER_ISSUE: ClassVar[int] = 99
    SLICE_ID: ClassVar[str] = "slice-11"
    SESSION_OF_THE_IMPLEMENTER: ClassVar[str] = HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER
    SESSION_OF_THE_JUDGE: ClassVar[str] = HarnessEnvelopeMother.SESSION_OF_THE_JUDGE
    SESSION_OF_ANOTHER_FEATURE: ClassVar[str] = "5e0f7c1a-1a2b-4c3d-9e8f-0a1b2c3d4e5f"

    @classmethod
    def of_the_implementer(cls) -> HarnessCall:
        return HarnessCall(
            repo=cls.REPO,
            issue=cls.ISSUE,
            slice_id=cls.SLICE_ID,
            step=Step.IMPLEMENT,
            session=cls.SESSION_OF_THE_IMPLEMENTER,
        )

    @classmethod
    def of_the_judge(cls) -> HarnessCall:
        return HarnessCall(
            repo=cls.REPO, issue=cls.ISSUE, slice_id=cls.SLICE_ID, step=Step.VERIFY, session=cls.SESSION_OF_THE_JUDGE
        )

    @classmethod
    def of_the_implementer_of_another_feature(cls) -> HarnessCall:
        return HarnessCall(
            repo=cls.OTHER_REPO,
            issue=cls.OTHER_ISSUE,
            slice_id=cls.SLICE_ID,
            step=Step.IMPLEMENT,
            session=cls.SESSION_OF_ANOTHER_FEATURE,
        )
