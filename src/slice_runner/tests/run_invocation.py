from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.application.actions.conduct_slice import ConductSliceParams
from slice_runner.domain.budgets import Budgets
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.metrics_invocation import MetricsInvocation
from slice_runner.tests.doubles import Answer, AnsweringByArgv
from slice_runner.tests.mothers.gh_conversation_mother import GhConversationMother

if TYPE_CHECKING:
    from pathlib import Path


class RunInvocation:
    def __init__(
        self,
        *,
        children: str,
        answers: tuple[Answer, ...] = (),
        parent: str = GhConversationMother.parent_of_one_slice(),
    ) -> None:
        self.process = AnsweringByArgv(
            Answer(to=("gh", "issue", "view", "body,subIssuesSummary"), stdout=parent),
            Answer(to=("gh", "issue", "list"), stdout=children),
            *answers,
            Answer(to=("gh", "issue", "view", "body"), stdout=GhConversationMother.body_of_the_subissue()),
            Answer(to=("gh", "issue", "edit")),
            Answer(to=("gh", "issue", "comment")),
            Answer(to=(MetricsInvocation.EXECUTABLE, "record")),
        )

    def conduct(
        self,
        *,
        logs: Path,
        base: str = GhConversationMother.BASE,
        slice_id: str | None = None,
        budgets: Budgets | None = None,
    ) -> int:
        return Cli(process=self.process, budgets=budgets or Budgets()).run(
            self.params(logs=logs, base=base, slice_id=slice_id)
        )

    @staticmethod
    def params(*, logs: Path, base: str = GhConversationMother.BASE, slice_id: str | None = None) -> ConductSliceParams:
        return ConductSliceParams(
            repo=GhConversationMother.REPO,
            issue=GhConversationMother.ISSUE,
            worktree=GhConversationMother.WORKTREE,
            base=base,
            logs=logs,
            slice_id=slice_id,
        )
