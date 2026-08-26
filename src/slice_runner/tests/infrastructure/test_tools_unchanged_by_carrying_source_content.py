from __future__ import annotations

from slice_runner.infrastructure.conflict_resolver_brief import ConflictResolverBrief
from slice_runner.infrastructure.slice_implementer_brief import SliceImplementerBrief
from slice_runner.infrastructure.slice_verifier_judge import SliceVerifierJudge
from slice_runner.infrastructure.understanding_brief import UnderstandingBrief


class TestNoToolsetChangedWhenSourcesStartedCarryingTheirContent:
    def test_the_implementer_still_gets_the_tools_it_needs_to_read_the_repo_and_run_its_cycle(self) -> None:
        assert SliceImplementerBrief.TOOLS == ("Read", "Write", "Edit", "Bash", "Grep", "Glob", "Skill")

    def test_the_understanding_writer_still_gets_only_the_reading_tools(self) -> None:
        assert UnderstandingBrief.TOOLS == ("Read", "Grep", "Glob", "Skill")

    def test_the_judge_still_gets_only_the_reading_tools(self) -> None:
        assert SliceVerifierJudge.TOOLS == ("Read", "Grep", "Glob", "Skill")

    def test_the_conflict_resolver_still_gets_only_the_tools_it_needs_to_edit_the_conflicting_files(self) -> None:
        assert ConflictResolverBrief.TOOLS == ("Read", "Write", "Edit", "Grep", "Glob")
