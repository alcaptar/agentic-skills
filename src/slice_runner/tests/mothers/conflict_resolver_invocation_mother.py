from __future__ import annotations

from slice_runner.infrastructure.conflict_resolver_invocation import ConflictResolverInvocation
from slice_runner.tests.doubles import RecordedSourceReader
from slice_runner.tests.mothers.merge_conflict_mother import MergeConflictMother


class ConflictResolverInvocationMother:
    @staticmethod
    def of_one_conflicting_file() -> ConflictResolverInvocation:
        return ConflictResolverInvocation(
            conflict=MergeConflictMother.of_one_conflicting_file(), reader=RecordedSourceReader()
        )

    @staticmethod
    def without_sources() -> ConflictResolverInvocation:
        return ConflictResolverInvocation(conflict=MergeConflictMother.without_sources(), reader=RecordedSourceReader())
