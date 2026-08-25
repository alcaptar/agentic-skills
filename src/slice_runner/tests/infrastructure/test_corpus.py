from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.clock import Clock
from slice_runner.infrastructure.claude_config import ClaudeConfig
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

_STAMP = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)


class WrittenCorpus:
    @staticmethod
    def verdicts_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "log" / "verdicts.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

    @staticmethod
    def diffs_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "log" / "diffs.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


class WithTheCorpusOutOfTheRealHome:
    @pytest.fixture(autouse=True)
    def corpus_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

    @staticmethod
    def frozen_at(stamp: datetime = _STAMP) -> Mock:
        clock: Mock = create_autospec(Clock, spec_set=True, instance=True)
        clock.now.return_value = stamp
        return clock


class TestTheRecordThatIsWritten(WithTheCorpusOutOfTheRealHome):
    def test_a_verification_is_written_as_the_run_it_came_from_and_the_verdict_the_judge_gave(
        self, tmp_path: Path
    ) -> None:
        LocalCorpus(clock=self.frozen_at()).record(CorpusEntryMother.of_the_slice())

        assert WrittenCorpus.verdicts_under(tmp_path) == [
            {
                "repo": CorpusEntryMother.REPO,
                "issue": CorpusEntryMother.ISSUE,
                "slice_id": CorpusEntryMother.SLICE_ID,
                "verify_round": CorpusEntryMother.VERIFY_ROUND,
                "session": CorpusEntryMother.SESSION,
                "verdict": {"ruling": "PASS", "findings": []},
                "severity_counts": {"high": 0, "medium": 0, "low": 0},
                "ts": _STAMP.isoformat(),
            }
        ]

    def test_the_diff_is_written_apart_next_to_the_identity_that_ties_it_back_to_its_verdict(
        self, tmp_path: Path
    ) -> None:
        LocalCorpus(clock=self.frozen_at()).record(CorpusEntryMother.of_the_slice())

        assert WrittenCorpus.diffs_under(tmp_path) == [
            {
                "slice_id": CorpusEntryMother.SLICE_ID,
                "diff": SliceDiffMother.TEXT,
                "repo": CorpusEntryMother.REPO,
                "issue": CorpusEntryMother.ISSUE,
                "verify_round": CorpusEntryMother.VERIFY_ROUND,
                "session": CorpusEntryMother.SESSION,
                "ts": _STAMP.isoformat(),
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

        LocalCorpus(clock=self.frozen_at()).record(CorpusEntryMother.of_the_slice(verdict=vetoed))

        assert WrittenCorpus.verdicts_under(tmp_path)[0]["severity_counts"] == {"high": 2, "medium": 1, "low": 0}


class TestTheCorpusOnlyGrows(WithTheCorpusOutOfTheRealHome):
    def test_a_second_verification_is_appended_instead_of_overwriting_the_first(self, tmp_path: Path) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())

        corpus.record(CorpusEntryMother.of_the_slice(slice_id="slice-01"))
        corpus.record(CorpusEntryMother.of_the_slice(slice_id="slice-02"))

        assert [record["slice_id"] for record in WrittenCorpus.verdicts_under(tmp_path)] == ["slice-01", "slice-02"]
        assert [record["slice_id"] for record in WrittenCorpus.diffs_under(tmp_path)] == ["slice-01", "slice-02"]

    def test_two_features_that_happen_to_share_a_slice_id_still_keep_their_own_repo_and_issue_apart(
        self, tmp_path: Path
    ) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())

        corpus.record(CorpusEntryMother.of_the_slice(repo="alcaptar/agentic-skills", issue=45))
        corpus.record(CorpusEntryMother.of_the_slice(repo="alcaptar/another-feature", issue=99))

        assert [(record["repo"], record["issue"]) for record in WrittenCorpus.verdicts_under(tmp_path)] == [
            ("alcaptar/agentic-skills", 45),
            ("alcaptar/another-feature", 99),
        ]


class TestTheHeavyDiffStaysOutOfTheVerdictLedger(WithTheCorpusOutOfTheRealHome):
    def test_counting_findings_never_needs_to_load_the_diff_of_any_verdict(self, tmp_path: Path) -> None:
        LocalCorpus(clock=self.frozen_at()).record(CorpusEntryMother.of_the_slice())

        for record in WrittenCorpus.verdicts_under(tmp_path):
            assert "diff" not in record


class TestWhereTheCorpusLives:
    def test_the_directory_is_created_when_it_is_not_there_so_the_first_pair_is_not_lost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "never-used-before"))

        LocalCorpus(clock=WithTheCorpusOutOfTheRealHome.frozen_at()).record(CorpusEntryMother.of_the_slice())

        assert (tmp_path / "never-used-before" / "slice-runner" / "log" / "verdicts.jsonl").exists()
        assert (tmp_path / "never-used-before" / "slice-runner" / "log" / "diffs.jsonl").exists()

    def test_without_the_variable_it_falls_back_to_the_home_of_the_tool_and_expands_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(ClaudeConfig.VARIABLE, raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))

        LocalCorpus(clock=WithTheCorpusOutOfTheRealHome.frozen_at()).record(CorpusEntryMother.of_the_slice())

        assert (tmp_path / ".claude" / "slice-runner" / "log" / "verdicts.jsonl").exists()


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

        assert len(WrittenCorpus.verdicts_under(tmp_path)) == 1
        assert len(WrittenCorpus.diffs_under(tmp_path)) == 1
        assert list(repo.rglob("verdicts.jsonl")) == []
        assert list(repo.rglob("diffs.jsonl")) == []
