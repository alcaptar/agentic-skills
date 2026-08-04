from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from slice_runner.application.actions.verify_slice import VerifySliceParams
from slice_runner.domain.judge import Judge
from slice_runner.domain.slice_diff import SliceDiff
from slice_runner.domain.slice_under_review import SliceUnderReview


class SliceDiffMother:
    TOUCHED: ClassVar[tuple[str, ...]] = ("src/mod.py", "src/tests/test_mod.py")
    TEXT: ClassVar[str] = (
        "diff --git a/src/mod.py b/src/mod.py\n"
        "--- a/src/mod.py\n"
        "+++ b/src/mod.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-    return 1\n"
        "+    return 2\n"
    )

    @classmethod
    def of_the_slice(cls, *, files: tuple[str, ...] | None = None, text: str | None = None) -> SliceDiff:
        return SliceDiff(text=text if text is not None else cls.TEXT, files=files or cls.TOUCHED)


class VerifySliceParamsMother:
    BASE: ClassVar[str] = "master"

    @classmethod
    def against_the_base(cls) -> VerifySliceParams:
        return VerifySliceParams(repo=SliceUnderReviewMother.REPO, base=cls.BASE)


class SliceUnderReviewMother:
    REPO: ClassVar[str] = "/repos/project"

    @classmethod
    def of_the_slice(
        cls, *, repo: str | None = None, files: tuple[str, ...] | None = None, text: str | None = None
    ) -> SliceUnderReview:
        return SliceUnderReview(repo=repo or cls.REPO, diff=SliceDiffMother.of_the_slice(files=files, text=text))


class JudgeMother:
    RUBRIC: ClassVar[str] = "You are the adversarial verifier."
    TOOLS: ClassVar[tuple[str, ...]] = ("Read", "Grep", "Glob", "Skill")
    YARDSTICK: ClassVar[Path] = Path("/toolbox/skills")

    @classmethod
    def adversarial(cls) -> Judge:
        return Judge(rubric=cls.RUBRIC, tools=cls.TOOLS)

    @classmethod
    def reading_the_repo_and_its_yardstick(cls) -> Judge:
        return cls.adversarial().also_reading(Path(SliceUnderReviewMother.REPO), cls.YARDSTICK)
