from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from slice_runner.domain.slice_status import SliceStatus

if TYPE_CHECKING:
    from slice_runner.domain.call_spend_log import CallSpendLog
    from slice_runner.domain.call_trace import CallTrace
    from slice_runner.domain.forum import Forum
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.metrics_log import MetricsLog
    from slice_runner.domain.run_repository import RunRepository
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class ShowFeatureStatusParams:
    repo: str
    issue: int


class ShowFeatureStatus:
    def __init__(
        self,
        *,
        repository: RunRepository,
        forum: Forum,
        metrics: MetricsLog,
        trace: CallTrace,
        spend_log: CallSpendLog,
    ) -> None:
        self._repository = repository
        self._forum = forum
        self._metrics = metrics
        self._trace = trace
        self._spend_log = spend_log

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
                spend=self._spend_of(repo=params.repo, child=child),
            )
            for child in children
        )

    def _spend_of(self, *, repo: str, child: SubIssue) -> HarnessSpend:
        calls = self._trace.calls_of(repo=repo, issue=child.number, slice_id=child.slice_id.canonical)
        sessions = tuple(call.session for call in calls)

        return self._spend_log.spend_of(sessions)
