from __future__ import annotations

from dataclasses import replace
from typing import ClassVar

from slice_runner.infrastructure.understanding_invocation import UnderstandingInvocation
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother


class UnderstandingInvocationMother:
    REPO: ClassVar[str] = "alcaptar/agentic-skills"
    WORKTREE: ClassVar[str] = "/repos/agentic-skills"

    @classmethod
    def of_the_chosen_slice(cls) -> UnderstandingInvocation:
        return UnderstandingInvocation(
            subissue=SubIssueMother.pending(),
            parent=ParentIssueMother.with_sources_and_controls(),
            repo=cls.REPO,
            worktree=cls.WORKTREE,
        )

    @classmethod
    def of_a_repo_exempt_from_controls(cls) -> UnderstandingInvocation:
        return replace(cls.of_the_chosen_slice(), parent=ParentIssueMother.with_exempt_controls())
