from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.cited_source import CitedSource
from slice_runner.domain.exceptions import SourcesBudgetExceededError, UnreadableSourceError
from slice_runner.domain.source import Source, SourceKind
from slice_runner.infrastructure.process_source_reader import ProcessSourceReader
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
class TestReadingADeclaredSource:
    def test_the_content_of_an_existing_file_is_returned_cited_by_its_source(self, tmp_path: Path) -> None:
        (tmp_path / "doc.md").write_text("la regla es esta", encoding="utf-8")
        reader = ProcessSourceReader(process=Real.process(), budgets=Budgets())
        source = Source(kind=SourceKind.DOC, path="doc.md")

        cited = reader.read_all(worktree=str(tmp_path), sources=(source,))

        assert cited == (CitedSource(source=source, content="la regla es esta"),)

    def test_several_declared_sources_are_all_read_and_cited_in_order(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("contenido de a", encoding="utf-8")
        (tmp_path / "b.md").write_text("contenido de b", encoding="utf-8")
        reader = ProcessSourceReader(process=Real.process(), budgets=Budgets())
        a, b = Source(kind=SourceKind.DOC, path="a.md"), Source(kind=SourceKind.DOC, path="b.md")

        cited = reader.read_all(worktree=str(tmp_path), sources=(a, b))

        assert cited == (
            CitedSource(source=a, content="contenido de a"),
            CitedSource(source=b, content="contenido de b"),
        )

    def test_a_declared_source_that_does_not_exist_is_unreadable_before_any_prompt_is_built(
        self, tmp_path: Path
    ) -> None:
        reader = ProcessSourceReader(process=Real.process(), budgets=Budgets())
        source = Source(kind=SourceKind.DOC, path="missing.md")

        with pytest.raises(UnreadableSourceError, match=r"missing\.md"):
            reader.read_all(worktree=str(tmp_path), sources=(source,))


@pytest.mark.integration
class TestTheSizeCapOnDeclaredSources:
    def test_content_exactly_at_the_cap_is_returned_without_raising(self, tmp_path: Path) -> None:
        (tmp_path / "doc.md").write_text("a" * 10, encoding="utf-8")
        reader = ProcessSourceReader(process=Real.process(), budgets=Budgets(sources_max_chars=10))
        source = Source(kind=SourceKind.DOC, path="doc.md")

        cited = reader.read_all(worktree=str(tmp_path), sources=(source,))

        assert cited[0].content == "a" * 10

    def test_content_one_character_over_the_cap_stops_the_run_instead_of_sending_a_prompt(self, tmp_path: Path) -> None:
        (tmp_path / "doc.md").write_text("a" * 11, encoding="utf-8")
        reader = ProcessSourceReader(process=Real.process(), budgets=Budgets(sources_max_chars=10))
        source = Source(kind=SourceKind.DOC, path="doc.md")

        with pytest.raises(SourcesBudgetExceededError):
            reader.read_all(worktree=str(tmp_path), sources=(source,))

    def test_the_message_names_every_source_and_how_much_it_weighs_against_the_cap(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("a" * 7, encoding="utf-8")
        (tmp_path / "b.md").write_text("b" * 4, encoding="utf-8")
        reader = ProcessSourceReader(process=Real.process(), budgets=Budgets(sources_max_chars=10))
        a, b = Source(kind=SourceKind.DOC, path="a.md"), Source(kind=SourceKind.DOC, path="b.md")

        with pytest.raises(SourcesBudgetExceededError, match=r"a\.md: 7 characters.*b\.md: 4 characters"):
            reader.read_all(worktree=str(tmp_path), sources=(a, b))
