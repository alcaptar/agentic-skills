from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from slice_runner.domain.slice_status import SliceStatus

if TYPE_CHECKING:
    from slice_runner.domain.forum import Forum
    from slice_runner.domain.metrics_log import MetricsLog
    from slice_runner.domain.run_repository import RunRepository


@dataclass(frozen=True, kw_only=True, slots=True)
class ShowFeatureStatusParams:
    repo: str
    issue: int


class ShowFeatureStatus:
    def __init__(self, *, repository: RunRepository, forum: Forum, metrics: MetricsLog) -> None:
        self._repository = repository
        self._forum = forum
        self._metrics = metrics

    def execute(self, params: ShowFeatureStatusParams) -> tuple[SliceStatus, ...]:
        overview = self._repository.read_parent(repo=params.repo, issue=params.issue, slice_repo=None)
        children = self._repository.read_children(
            repo=params.repo, parent=params.issue, expected=overview.subissue_count
        )
        pulls = self._forum.open_pull_requests(repo=params.repo, branches=tuple(child.branch for child in children))
        pull_request_of = {pull.branch: pull.number for pull in pulls}
        records = self._metrics.closed_slices(
            repo=params.repo, since=datetime.min.replace(tzinfo=UTC), until=datetime.max.replace(tzinfo=UTC)
        )
        record_of = {record.issue: record for record in records}

        return tuple(
            SliceStatus(
                sub_issue=child,
                pull_request=pull_request_of.get(child.branch),
                record=record_of.get(child.number),
            )
            for child in children
        )
