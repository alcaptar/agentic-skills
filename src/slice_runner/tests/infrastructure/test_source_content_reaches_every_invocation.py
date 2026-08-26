from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from slice_runner.domain.alignment import Alignment
from slice_runner.domain.budgets import Budgets
from slice_runner.infrastructure.conflict_resolver_invocation import ConflictResolverInvocation
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.process_source_reader import ProcessSourceReader
from slice_runner.infrastructure.understanding_invocation import UnderstandingInvocation
from slice_runner.tests.doubles import RecordedSourceReader
from slice_runner.tests.mothers.assignment_mother import AssignmentMother
from slice_runner.tests.mothers.merge_conflict_mother import MergeConflictMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.verification_mother import JudgeMother, SliceUnderReviewMother
from slice_runner.tests.real_process import Real

_ROOT = Path(__file__).resolve().parents[4]
_LITERAL_LINE_OF_CLAUDE_MD = "# agentic-skills — instrucciones del repo"


@pytest.mark.integration
class TestEachInvocationCarriesTheLiteralContentOfItsDeclaredSource:
    @staticmethod
    def _real_reader() -> ProcessSourceReader:
        return ProcessSourceReader(process=Real.process(), budgets=Budgets())

    def test_the_implementer_carries_a_literal_line_of_the_declared_source(self) -> None:
        assignment = replace(AssignmentMother.of_the_first_round(), worktree=str(_ROOT))

        text = ImplementerInvocation(assignment=assignment, reader=self._real_reader()).text

        assert _LITERAL_LINE_OF_CLAUDE_MD in text

    def test_the_judge_carries_a_literal_line_of_the_declared_source(self) -> None:
        review = replace(SliceUnderReviewMother.of_the_slice(), worktree=str(_ROOT))

        text = JudgeInvocation(judge=JudgeMother.adversarial(), review=review, reader=self._real_reader()).text

        assert _LITERAL_LINE_OF_CLAUDE_MD in text

    def test_the_understanding_writer_carries_a_literal_line_of_the_declared_source(self) -> None:
        invocation = UnderstandingInvocation(
            subissue=SubIssueMother.pending(),
            parent=ParentIssueMother.with_sources_and_controls(),
            repo=AssignmentMother.REPO,
            worktree=str(_ROOT),
            alignment=Alignment(),
            reader=self._real_reader(),
        )

        assert _LITERAL_LINE_OF_CLAUDE_MD in invocation.text

    def test_the_conflict_resolver_carries_a_literal_line_of_the_declared_source(self) -> None:
        conflict = replace(MergeConflictMother.of_one_conflicting_file(), worktree=str(_ROOT))

        text = ConflictResolverInvocation(conflict=conflict, reader=self._real_reader()).text

        assert _LITERAL_LINE_OF_CLAUDE_MD in text


class TestTheFourInvocationsAgreeOnTheSameSourcesTextForTheSameSources:
    @staticmethod
    def _fuentes_section(text: str) -> str:
        lines = text.splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith("- fuentes de convencion"))
        end = start + 1
        while end < len(lines) and lines[end].startswith(" "):
            end += 1

        return "\n".join(lines[start:end])

    def test_the_fuentes_section_is_character_for_character_identical_across_the_four(self) -> None:
        reader = RecordedSourceReader(contents={"CLAUDE.md": "linea unica de la convencion"})

        implementer_text = ImplementerInvocation(assignment=AssignmentMother.of_the_first_round(), reader=reader).text
        judge_text = JudgeInvocation(
            judge=JudgeMother.adversarial(), review=SliceUnderReviewMother.of_the_slice(), reader=reader
        ).text
        understanding_text = UnderstandingInvocation(
            subissue=SubIssueMother.pending(),
            parent=ParentIssueMother.with_sources_and_controls(),
            repo=AssignmentMother.REPO,
            worktree=AssignmentMother.WORKTREE,
            alignment=Alignment(),
            reader=reader,
        ).text
        resolver_text = ConflictResolverInvocation(
            conflict=MergeConflictMother.of_one_conflicting_file(), reader=reader
        ).text

        sections = {
            self._fuentes_section(implementer_text),
            self._fuentes_section(judge_text),
            self._fuentes_section(understanding_text),
            self._fuentes_section(resolver_text),
        }
        assert len(sections) == 1


class TestTheFourInvocationsAgreeOnTheSameWorkingDirectory:
    def test_the_four_invocations_agree_that_the_cwd_is_the_worktree_and_not_the_repo_slug(self) -> None:
        worktree = AssignmentMother.WORKTREE
        reader = RecordedSourceReader()

        implementer = ImplementerInvocation(assignment=AssignmentMother.of_the_first_round(), reader=reader)
        judge = JudgeInvocation(
            judge=JudgeMother.adversarial(),
            review=replace(SliceUnderReviewMother.of_the_slice(), worktree=worktree),
            reader=reader,
        )
        understanding = UnderstandingInvocation(
            subissue=SubIssueMother.pending(),
            parent=ParentIssueMother.with_sources_and_controls(),
            repo=AssignmentMother.REPO,
            worktree=worktree,
            alignment=Alignment(),
            reader=reader,
        )
        resolver = ConflictResolverInvocation(
            conflict=replace(MergeConflictMother.of_one_conflicting_file(), worktree=worktree), reader=reader
        )

        assert implementer.cwd == judge.cwd == understanding.cwd == resolver.cwd == worktree
