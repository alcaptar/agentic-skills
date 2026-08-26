from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.conflict_resolution import ConflictResolution
from slice_runner.domain.conflict_resolver import ConflictResolver
from slice_runner.domain.exceptions import PermissionDeniedError
from slice_runner.domain.step import Step
from slice_runner.infrastructure.conflict_resolution_report_payload import ConflictResolutionReportPayload
from slice_runner.infrastructure.conflict_resolver_invocation import ConflictResolverInvocation
from slice_runner.infrastructure.harness_invocation_runner import HarnessCallSubject

if TYPE_CHECKING:
    from slice_runner.domain.merge_conflict import MergeConflict
    from slice_runner.domain.source_reader import SourceReader
    from slice_runner.infrastructure.harness_invocation_runner import HarnessInvocationRunner
    from slice_runner.infrastructure.harness_output import HarnessOutput


class ClaudeConflictResolver(ConflictResolver):
    def __init__(self, *, calls: HarnessInvocationRunner, reader: SourceReader) -> None:
        self._calls = calls
        self._reader = reader

    def resolve(self, conflict: MergeConflict) -> ConflictResolution:
        invocation = ConflictResolverInvocation(conflict=conflict, reader=self._reader)
        envelope = self._calls.call(
            invocation,
            step=Step.CATCH_UP,
            subject=HarnessCallSubject(
                repo=conflict.repo, issue=conflict.issue, slice_id=conflict.slice_id, worktree=conflict.worktree
            ),
        )
        with envelope.measuring():
            self._reject_denials(envelope)
            ConflictResolutionReportPayload.from_dict(envelope.structured_output)

        return ConflictResolution(spend=envelope.to_domain())

    @staticmethod
    def _reject_denials(envelope: HarnessOutput) -> None:
        denials = tuple(denial.denied_action for denial in envelope.permission_denials)
        if denials:
            raise PermissionDeniedError(
                f"the harness denied {len(denials)} permission(s), so there is no resolution to trust: "
                f"{', '.join(denials)}"
            )
