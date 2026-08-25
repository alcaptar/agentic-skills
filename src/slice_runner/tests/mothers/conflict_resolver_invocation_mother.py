from __future__ import annotations

from dataclasses import replace

from slice_runner.infrastructure.conflict_resolver_invocation import ConflictResolverInvocation
from slice_runner.tests.doubles import RecordedSourceReader
from slice_runner.tests.mothers.merge_conflict_mother import MergeConflictMother


class ConflictResolverInvocationMother:
    @classmethod
    def of_one_conflicted_file(cls) -> ConflictResolverInvocation:
        return ConflictResolverInvocation(
            conflict=MergeConflictMother.of_one_conflicted_file(), reader=RecordedSourceReader()
        )

    @classmethod
    def without_sources(cls) -> ConflictResolverInvocation:
        return replace(cls.of_one_conflicted_file(), conflict=MergeConflictMother.without_sources())
