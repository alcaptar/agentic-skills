from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.infrastructure.local_corpus import LocalCorpus
from slice_runner.tests.doubles import RealExceptTheJudge
from slice_runner.tests.git_repo import Git
from slice_runner.tests.mothers.corpus_entry_mother import CorpusEntryMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother, JudgeVerdictMother
from slice_runner.tests.mothers.repo_mother import RepoMother
from slice_runner.tests.mothers.verdict_mother import FindingMother, VerdictMother
from slice_runner.tests.mothers.verification_mother import SliceDiffMother

if TYPE_CHECKING:
    from pathlib import Path


class WrittenCorpus:
    @staticmethod
    def records_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "corpus" / "verdicts.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


class WithTheCorpusOutOfTheRealHome:
    @pytest.fixture(autouse=True)
    def corpus_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(LocalCorpus.CONFIG_VARIABLE, str(tmp_path))


class TestTheRecordThatIsWritten(WithTheCorpusOutOfTheRealHome):
    def test_a_verification_is_written_as_the_slice_the_diff_and_the_verdict_the_judge_gave(
        self, tmp_path: Path
    ) -> None:
        LocalCorpus().record(CorpusEntryMother.of_the_slice())

        assert WrittenCorpus.records_under(tmp_path) == [
            {
                "slice_id": CorpusEntryMother.SLICE_ID,
                "diff": SliceDiffMother.TEXT,
                "verdict": {"veredicto": "PASA", "hallazgos": []},
                "severity_counts": {"alta": 0, "media": 0, "baja": 0},
            }
        ]

    def test_the_count_by_severity_travels_written_down_so_nobody_downstream_recounts_the_findings(
        self, tmp_path: Path
    ) -> None:
        vetoed = VerdictMother.failing(
            FindingMother.without_line(),
            FindingMother.without_line(path="src/y.py"),
            FindingMother.with_line(),
        )

        LocalCorpus().record(CorpusEntryMother.of_the_slice(verdict=vetoed))

        assert WrittenCorpus.records_under(tmp_path)[0]["severity_counts"] == {"alta": 2, "media": 1, "baja": 0}


class TestTheCorpusOnlyGrows(WithTheCorpusOutOfTheRealHome):
    def test_a_second_verification_is_appended_instead_of_overwriting_the_first(self, tmp_path: Path) -> None:
        corpus = LocalCorpus()

        corpus.record(CorpusEntryMother.of_the_slice(slice_id="slice-01"))
        corpus.record(CorpusEntryMother.of_the_slice(slice_id="slice-02"))

        assert [record["slice_id"] for record in WrittenCorpus.records_under(tmp_path)] == ["slice-01", "slice-02"]


class TestWhereTheCorpusLives:
    def test_the_directory_is_created_when_it_is_not_there_so_the_first_pair_is_not_lost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(LocalCorpus.CONFIG_VARIABLE, str(tmp_path / "never-used-before"))

        LocalCorpus().record(CorpusEntryMother.of_the_slice())

        assert (tmp_path / "never-used-before" / "slice-runner" / "corpus" / "verdicts.jsonl").exists()

    def test_without_the_variable_it_falls_back_to_the_home_of_the_tool_and_expands_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(LocalCorpus.CONFIG_VARIABLE, raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))

        LocalCorpus().record(CorpusEntryMother.of_the_slice())

        assert (tmp_path / ".claude" / "slice-runner" / "corpus" / "verdicts.jsonl").exists()


@pytest.mark.integration
class TestNothingOfTheCorpusCanReachAPullRequest(WithTheCorpusOutOfTheRealHome):
    @staticmethod
    def _verified(repo: Path) -> None:
        process = RealExceptTheJudge(HarnessEnvelopeMother.carrying(JudgeVerdictMother.passing()))

        code = Cli(process=process, budgets=Budgets()).verify(
            repo=str(repo), base=Git.BASE_BRANCH, slice_id=CorpusEntryMother.SLICE_ID
        )

        assert code == ExitCode.OK

    def test_a_verification_leaves_the_tree_of_the_repo_exactly_as_it_found_it(self, tmp_path: Path) -> None:
        repo = RepoMother.with_the_slice_committed(tmp_path)

        self._verified(repo)

        assert Git.run(repo, "status", "--porcelain") == ""

    def test_the_pair_lands_outside_the_repo_where_no_git_add_of_the_slice_can_sweep_it_in(
        self, tmp_path: Path
    ) -> None:
        repo = RepoMother.with_the_slice_committed(tmp_path)

        self._verified(repo)

        assert len(WrittenCorpus.records_under(tmp_path)) == 1
        assert list(repo.rglob("verdicts.jsonl")) == []
