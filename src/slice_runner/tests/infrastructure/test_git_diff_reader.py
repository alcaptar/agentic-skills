from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import EmptyIndexError, UnresolvableRepoOrBaseError
from slice_runner.infrastructure.git_diff_reader import GitDiffReader
from slice_runner.tests.git_repo import Git
from slice_runner.tests.mothers.repo_mother import RepoMother
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
class TestWhatItReads:
    def test_the_diff_comes_back_as_text_so_nobody_downstream_has_to_open_a_file(self, tmp_path: Path) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        read = self._reader().read(repo=str(repo), base=Git.BASE_BRANCH)

        assert "-    return 1" in read.text
        assert "+    return 2" in read.text

    def test_reading_the_diff_leaves_no_file_behind_neither_beside_the_repo_nor_inside_it(self, tmp_path: Path) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        staged_before = Git.run(repo, "status", "--porcelain")

        self._reader().read(repo=str(repo), base=Git.BASE_BRANCH)

        assert [entry.name for entry in tmp_path.iterdir()] == [repo.name]
        assert Git.run(repo, "status", "--porcelain") == staged_before

    def test_the_scope_is_every_staged_file_and_not_a_path_to_a_listing(self, tmp_path: Path) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        read = self._reader().read(repo=str(repo), base=Git.BASE_BRANCH)

        assert read.files == ("mod.py",)

    def test_the_stats_count_the_one_file_touched_and_its_added_and_deleted_lines(self, tmp_path: Path) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        read = self._reader().read(repo=str(repo), base=Git.BASE_BRANCH)

        assert (read.stats.files_changed, read.stats.lines_added, read.stats.lines_deleted) == (1, 1, 1)

    def test_a_second_file_staged_is_counted_into_the_same_stats(self, tmp_path: Path) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        (repo / "other.py").write_text("def g() -> int:\n    return 3\n", encoding="utf-8")
        Git.run(repo, "add", "other.py")

        read = self._reader().read(repo=str(repo), base=Git.BASE_BRANCH)

        assert (read.stats.files_changed, read.stats.lines_added, read.stats.lines_deleted) == (2, 3, 1)

    def test_a_binary_file_staged_is_counted_as_a_file_changed_with_no_lines_because_git_reports_none(
        self, tmp_path: Path
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        (repo / "asset.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")
        Git.run(repo, "add", "asset.png")

        read = self._reader().read(repo=str(repo), base=Git.BASE_BRANCH)

        assert (read.stats.files_changed, read.stats.lines_added, read.stats.lines_deleted) == (2, 1, 1)

    @staticmethod
    def _reader() -> GitDiffReader:
        return GitDiffReader(process=Real.process())


@pytest.mark.integration
class TestWhatItRefusesToRead:
    def test_an_unstaged_change_to_a_tracked_file_is_not_in_the_diff_because_the_index_is_what_commits(
        self, tmp_path: Path
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        (repo / "mod.py").write_text("def f() -> int:\n    return 999\n", encoding="utf-8")

        read = GitDiffReader(process=Real.process()).read(repo=str(repo), base=Git.BASE_BRANCH)

        assert "999" not in read.text
        assert "+    return 2" in read.text

    def test_nothing_staged_is_an_empty_index_and_not_an_empty_diff(self, tmp_path: Path) -> None:
        repo = RepoMother.with_nothing_staged(tmp_path)

        with pytest.raises(EmptyIndexError, match="nothing staged"):
            GitDiffReader(process=Real.process()).read(repo=str(repo), base=Git.BASE_BRANCH)

    def test_a_base_that_does_not_resolve_is_told_apart_from_an_empty_index(self, tmp_path: Path) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        with pytest.raises(UnresolvableRepoOrBaseError, match="not-a-base"):
            GitDiffReader(process=Real.process()).read(repo=str(repo), base="not-a-base")

    def test_a_directory_that_is_not_a_repo_is_told_apart_too(self, tmp_path: Path) -> None:
        outside = RepoMother.outside_git(tmp_path)

        with pytest.raises(UnresolvableRepoOrBaseError):
            GitDiffReader(process=Real.process()).read(repo=str(outside), base=Git.BASE_BRANCH)
