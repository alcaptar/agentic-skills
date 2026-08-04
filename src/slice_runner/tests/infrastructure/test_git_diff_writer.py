from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import EmptyIndexError, UnresolvableRepoOrBaseError
from slice_runner.infrastructure.git_diff_writer import GitDiffWriter
from slice_runner.infrastructure.local_process import LocalProcess
from slice_runner.tests.git_repo import Git
from slice_runner.tests.mothers.repo_mother import RepoMother

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
class TestWhatItWrites:
    def test_only_the_patch_lands_on_disk_because_the_scope_travels_in_the_prompt(self, tmp_path: Path) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        destination = tmp_path / "written"

        self._writer(destination).write(repo=str(repo), base=Git.BASE_BRANCH)

        assert [entry.name for entry in destination.iterdir()] == ["slice.diff"]

    def test_the_patch_is_the_diff_of_the_slice(self, tmp_path: Path) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        written = self._writer(tmp_path / "written").write(repo=str(repo), base=Git.BASE_BRANCH)

        patch = written.diff.read_text(encoding="utf-8")
        assert "-    return 1" in patch
        assert "+    return 2" in patch

    def test_the_scope_comes_back_in_memory_and_not_as_a_path(self, tmp_path: Path) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        written = self._writer(tmp_path / "written").write(repo=str(repo), base=Git.BASE_BRANCH)

        assert written.files == ("mod.py",)

    @staticmethod
    def _writer(destination: Path) -> GitDiffWriter:
        return GitDiffWriter(process=LocalProcess(), destination=destination)


@pytest.mark.integration
class TestWhatItJudgesUnwritable:
    def test_an_unstaged_change_to_a_tracked_file_is_not_in_the_patch_because_the_index_is_what_commits(
        self, tmp_path: Path
    ) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)
        (repo / "mod.py").write_text("def f() -> int:\n    return 999\n", encoding="utf-8")

        written = GitDiffWriter(process=LocalProcess(), destination=tmp_path / "w").write(
            repo=str(repo), base=Git.BASE_BRANCH
        )

        patch = written.diff.read_text(encoding="utf-8")
        assert "999" not in patch
        assert "+    return 2" in patch

    def test_nothing_staged_is_an_empty_index_and_not_an_empty_patch(self, tmp_path: Path) -> None:
        repo = RepoMother.with_nothing_staged(tmp_path)

        with pytest.raises(EmptyIndexError, match="nothing staged"):
            GitDiffWriter(process=LocalProcess(), destination=tmp_path / "w").write(
                repo=str(repo), base=Git.BASE_BRANCH
            )

    def test_nothing_is_written_when_there_is_nothing_to_verify(self, tmp_path: Path) -> None:
        repo = RepoMother.with_nothing_staged(tmp_path)
        destination = tmp_path / "w"

        with pytest.raises(EmptyIndexError):
            GitDiffWriter(process=LocalProcess(), destination=destination).write(repo=str(repo), base=Git.BASE_BRANCH)

        assert not destination.exists()

    def test_a_base_that_does_not_resolve_is_told_apart_from_an_empty_index(self, tmp_path: Path) -> None:
        repo = RepoMother.with_the_slice_staged(tmp_path)

        with pytest.raises(UnresolvableRepoOrBaseError, match="not-a-base"):
            GitDiffWriter(process=LocalProcess(), destination=tmp_path / "w").write(repo=str(repo), base="not-a-base")

    def test_a_directory_that_is_not_a_repo_is_told_apart_too(self, tmp_path: Path) -> None:
        outside = RepoMother.outside_git(tmp_path)

        with pytest.raises(UnresolvableRepoOrBaseError):
            GitDiffWriter(process=LocalProcess(), destination=tmp_path / "w").write(
                repo=str(outside), base=Git.BASE_BRANCH
            )
