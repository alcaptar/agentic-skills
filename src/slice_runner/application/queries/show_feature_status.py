from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.slice_status import SliceStatus

if TYPE_CHECKING:
    from slice_runner.domain.forum import Forum
    from slice_runner.domain.run_repository import RunRepository


@dataclass(frozen=True, kw_only=True, slots=True)
class ShowFeatureStatusParams:
    repo: str
    issue: int


class ShowFeatureStatus:
    def __init__(self, *, repository: RunRepository, forum: Forum) -> None:
        self._repository = repository
        self._forum = forum

    def execute(self, params: ShowFeatureStatusParams) -> tuple[SliceStatus, ...]:
        overview = self._repository.read_parent(repo=params.repo, issue=params.issue, slice_repo=None)
        children = self._repository.read_children(
            repo=params.repo, parent=params.issue, expected=overview.subissue_count
        )
        pulls = self._forum.open_pull_requests(repo=params.repo, branches=tuple(child.branch for child in children))
        pull_request_of = {pull.branch: pull.number for pull in pulls}

        return tuple(SliceStatus(sub_issue=child, pull_request=pull_request_of.get(child.branch)) for child in children)
