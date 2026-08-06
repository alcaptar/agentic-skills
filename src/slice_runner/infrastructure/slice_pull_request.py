from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.pull_request_writer import PullRequestWriter
from slice_runner.infrastructure.pull_request_body import PullRequestBody

if TYPE_CHECKING:
    from slice_runner.domain.sub_issue import SubIssue


class SlicePullRequest(PullRequestWriter):
    COMMIT_TYPE: ClassVar[str] = "feat"

    def title(self, subissue: SubIssue) -> str:
        return f"{self.COMMIT_TYPE}({subissue.name}): {subissue.summary}"

    def body(self, subissue: SubIssue) -> str:
        return PullRequestBody(
            intention=subissue.intention,
            criteria=subissue.criteria,
            debt=(),
            signal=subissue.signal,
            subissue=subissue.number,
        ).rendered()
