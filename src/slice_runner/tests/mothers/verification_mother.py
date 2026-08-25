from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from slice_runner.application.actions.verify_slice import VerifySliceParams
from slice_runner.domain.checklist_entry import ChecklistEntry
from slice_runner.domain.diff_stats import DiffStats
from slice_runner.domain.judge import Judge
from slice_runner.domain.slice_diff import SliceDiff
from slice_runner.domain.slice_under_review import SliceUnderReview
from slice_runner.domain.verification import Verification
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.verdict_mother import FindingMother, VerdictMother

if TYPE_CHECKING:
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.source import Source
    from slice_runner.domain.verdict import Verdict


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
    STATS: ClassVar[DiffStats] = DiffStats(files_changed=2, lines_added=1, lines_deleted=1)

    @classmethod
    def of_the_slice(
        cls, *, files: tuple[str, ...] | None = None, text: str | None = None, stats: DiffStats | None = None
    ) -> SliceDiff:
        return SliceDiff(
            text=text if text is not None else cls.TEXT, files=files or cls.TOUCHED, stats=stats or cls.STATS
        )


class VerifySliceParamsMother:
    BASE: ClassVar[str] = "master"

    @classmethod
    def against_the_base(cls) -> VerifySliceParams:
        return VerifySliceParams(
            repo=SliceUnderReviewMother.REPO,
            issue=SliceUnderReviewMother.ISSUE,
            worktree=SliceUnderReviewMother.WORKTREE,
            base=cls.BASE,
            slice_id=SliceUnderReviewMother.SLICE_ID,
            signal=SliceUnderReviewMother.signal(),
            excludes=SliceUnderReviewMother.excludes(),
            replaces=SliceUnderReviewMother.replaces(),
            prior_art="",
            criteria=SliceUnderReviewMother.criteria(),
            sources=SliceUnderReviewMother.sources(),
            checklist=SliceUnderReviewMother.checklist(),
        )


class SliceUnderReviewMother:
    REPO: ClassVar[str] = "alcaptar/agentic-skills"
    ISSUE: ClassVar[int] = 45
    WORKTREE: ClassVar[str] = "/repos/project"
    SLICE_ID: ClassVar[str] = "slice-05"
    SLICE_ID_WITH_A_USER_STORY: ClassVar[str] = "PROJ-1234-05"

    @classmethod
    def of_the_slice(
        cls,
        *,
        worktree: str | None = None,
        files: tuple[str, ...] | None = None,
        text: str | None = None,
        slice_id: str | None = None,
        excludes: str | None = None,
        replaces: str | None = None,
    ) -> SliceUnderReview:
        return SliceUnderReview(
            slice_id=slice_id or cls.SLICE_ID,
            repo=cls.REPO,
            issue=cls.ISSUE,
            worktree=worktree or cls.WORKTREE,
            diff=SliceDiffMother.of_the_slice(files=files, text=text),
            signal=cls.signal(),
            excludes=excludes if excludes is not None else cls.excludes(),
            replaces=replaces if replaces is not None else cls.replaces(),
            prior_art="",
            criteria=cls.criteria(),
            sources=cls.sources(),
            checklist=cls.checklist(),
        )

    @staticmethod
    def signal() -> str:
        return SubIssueMother.pending().signal

    @staticmethod
    def excludes() -> str:
        return SubIssueMother.pending().excludes

    @staticmethod
    def replaces() -> str:
        return SubIssueMother.pending().replaces

    @staticmethod
    def criteria() -> tuple[str, ...]:
        return SubIssueMother.pending().criteria

    @staticmethod
    def sources() -> tuple[Source, ...]:
        return ParentIssueMother.with_sources_and_controls().sources

    @staticmethod
    def checklist() -> tuple[ChecklistEntry, ...]:
        return (ChecklistEntry.of(SubIssueMother.closed()), ChecklistEntry.of(SubIssueMother.of_another_repo()))


class JudgeMother:
    RUBRIC: ClassVar[str] = "You are the adversarial verifier."
    TOOLS: ClassVar[tuple[str, ...]] = ("Read", "Grep", "Glob", "Skill")
    YARDSTICK: ClassVar[Path] = Path("/toolbox/skills")

    @classmethod
    def adversarial(cls) -> Judge:
        return Judge(rubric=cls.RUBRIC, tools=cls.TOOLS)

    @classmethod
    def reading_the_repo_and_its_yardstick(cls) -> Judge:
        return cls.adversarial().also_reading(Path(SliceUnderReviewMother.WORKTREE), cls.YARDSTICK)


class VerificationMother:
    DENIED_READ: ClassVar[str] = "Read /toolbox/skills/x.md"

    @staticmethod
    def passing() -> Verification:
        return Verification(
            verdict=VerdictMother.passing(),
            spend=HarnessSpendMother.of_the_judge_call(),
            diff_stats=SliceDiffMother.STATS,
        )

    @staticmethod
    def vetoing(verdict: Verdict) -> Verification:
        return Verification(
            verdict=verdict, spend=HarnessSpendMother.of_the_judge_call(), diff_stats=SliceDiffMother.STATS
        )

    @staticmethod
    def ordering_corrections(*findings: Finding) -> Verification:
        return Verification(
            verdict=VerdictMother.passing_with(*findings),
            spend=HarnessSpendMother.of_the_judge_call(),
            diff_stats=SliceDiffMother.STATS,
        )

    @staticmethod
    def approving_with_accepted_debt(*findings: Finding) -> Verification:
        chosen = findings or (FindingMother.low_severity(),)

        return Verification(
            verdict=VerdictMother.passing_with(*chosen),
            spend=HarnessSpendMother.of_the_judge_call(),
            diff_stats=SliceDiffMother.STATS,
        )

    @classmethod
    def failing_after_a_denied_read(cls) -> Verification:
        return Verification(
            verdict=VerdictMother.failing(),
            spend=HarnessSpendMother.of_the_judge_call(),
            diff_stats=SliceDiffMother.STATS,
            denied_reads=(cls.DENIED_READ,),
        )
