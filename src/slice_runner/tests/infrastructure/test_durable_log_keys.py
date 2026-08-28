from __future__ import annotations

import json
from typing import TYPE_CHECKING

from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.diff_stats import DiffStats
from slice_runner.domain.unrecorded_conversation_cause import UnrecordedConversationCause
from slice_runner.infrastructure.local_call_spend_log import LocalCallSpendLog
from slice_runner.infrastructure.local_call_trace import LocalCallTrace
from slice_runner.infrastructure.local_corpus import LocalCorpus
from slice_runner.infrastructure.local_event_log import LocalEventLog
from slice_runner.infrastructure.local_metrics_log import LocalMetricsLog
from slice_runner.infrastructure.local_tool_use_log import LocalToolUseLog
from slice_runner.infrastructure.tool_use_log import UnrecordedCallToolUse
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.mothers.closed_slice_mother import ClosedSliceMother
from slice_runner.tests.mothers.corpus_entry_mother import CorpusEntryMother
from slice_runner.tests.mothers.discarded_call_mother import DiscardedCallMother
from slice_runner.tests.mothers.event_mother import EventMother
from slice_runner.tests.mothers.harness_call_mother import HarnessCallMother
from slice_runner.tests.mothers.harness_call_spend_mother import HarnessCallSpendMother
from slice_runner.tests.mothers.harness_call_tool_use_mother import HarnessCallToolUseMother
from slice_runner.tests.mothers.verdict_mother import FindingMother, VerdictMother

if TYPE_CHECKING:
    from pathlib import Path

_STAMP = WithTheDurableStoresOutOfTheRealHome.STAMP


class ReadingTheLedger(WithTheDurableStoresOutOfTheRealHome):
    @staticmethod
    def rows_of(root: Path, name: str) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "runs" / f"{name}.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

    @staticmethod
    def flattened(value: object, prefix: str = "") -> set[str]:
        keys: set[str] = set()
        if isinstance(value, dict):
            for key, child in value.items():
                name = f"{prefix}.{key}" if prefix else key
                keys.add(name)
                keys |= ReadingTheLedger.flattened(child, name)
        elif isinstance(value, list):
            for child in value:
                keys |= ReadingTheLedger.flattened(child, prefix)

        return keys


class TestNoDurableStoreWritesAKeyInSpanish(ReadingTheLedger):
    def test_the_call_trace_keys_are_the_identity_of_the_call(self, tmp_path: Path) -> None:
        LocalCallTrace(clock=self.frozen_at()).record(HarnessCallMother.of_the_implementer())

        keys = self.flattened(self.rows_of(tmp_path, "calls")[0])

        assert keys == {"ts", "repo", "issue", "slice_id", "step", "session"}

    def test_the_spend_log_keys_are_the_session_and_the_spend_it_carries(self, tmp_path: Path) -> None:
        LocalCallSpendLog(clock=self.frozen_at()).record(HarnessCallSpendMother.of_the_implementer())

        keys = self.flattened(self.rows_of(tmp_path, "spend")[0])

        assert keys == {
            "ts",
            "repo",
            "issue",
            "slice_id",
            "session",
            "spend",
            "spend.cost_usd",
            "spend.turns",
            "spend.duration_ms",
            "spend.calls",
            "spend.models",
            "spend.input_tokens",
            "spend.output_tokens",
            "spend.cache_creation_tokens",
            "spend.cache_read_tokens",
            "spend.ttft_ms",
            "spend.duration_api_ms",
        }

    def test_the_metrics_log_keys_cover_every_optional_group_the_log_can_carry(self, tmp_path: Path) -> None:
        log = LocalMetricsLog(clock=self.frozen_at())
        stats = DiffStats(files_changed=4, lines_added=51, lines_deleted=9)
        log.record(
            ClosedSliceMother.merged_discarding_and_measuring_the_diff(DiscardedCallMother.of_a_failed_call(), stats)
        )
        log.record(ClosedSliceMother.blocked_indeterminate_because_of(CiIndeterminateCause.COMMAND_FAILED))

        rows = self.rows_of(tmp_path, "metrics")
        keys = self.flattened(rows[0]) | self.flattened(rows[1])

        assert keys == {
            "ts",
            "repo",
            "issue",
            "slice_id",
            "name",
            "verdict",
            "ci",
            "findings",
            "findings.high",
            "findings.medium",
            "findings.low",
            "findings_of_the_last_round",
            "findings_of_the_last_round.high",
            "findings_of_the_last_round.medium",
            "findings_of_the_last_round.low",
            "implement_retries",
            "control_retries",
            "ci_retries",
            "verify_retries",
            "correction_retries",
            "verify_discards",
            "understand_discards",
            "implement_discards",
            "harness",
            "harness.cost_usd",
            "harness.turns",
            "harness.duration_ms",
            "harness.calls",
            "harness.models",
            "harness.input_tokens",
            "harness.output_tokens",
            "harness.cache_creation_tokens",
            "harness.cache_read_tokens",
            "harness.ttft_ms",
            "harness.duration_api_ms",
            "discarded_call",
            "discarded_call.step",
            "discarded_call.cause",
            "discarded_call.reason",
            "ci_indeterminate_cause",
            "variant",
            "debt",
            "diff",
            "diff.files_changed",
            "diff.lines_added",
            "diff.lines_deleted",
            "budgets",
            "budgets.control_retries",
            "budgets.hygiene_retries",
            "budgets.verify_retries",
            "budgets.correction_retries",
            "budgets.ci_retries",
            "budgets.catch_up_retries",
            "budgets.indeterminate_ticks",
            "budgets.seconds_between_ticks",
            "budgets.ci_wait_seconds",
            "budgets.person_wait_seconds",
            "budgets.process_timeout_seconds",
            "budgets.slice_cost_usd",
            "budgets.gh_retries",
            "budgets.seconds_between_gh_retries",
            "budgets.sources_max_chars",
            "models_by_role",
            "models_by_role.understand",
            "models_by_role.implement",
            "models_by_role.verify",
        }

    def test_the_corpus_verdict_keys_cover_the_findings_a_verdict_carries(self, tmp_path: Path) -> None:
        entry = CorpusEntryMother.of_the_slice(verdict=VerdictMother.passing_with(FindingMother.with_line()))
        LocalCorpus(clock=self.frozen_at()).record(entry)

        keys = self.flattened(self.rows_of(tmp_path, "verdicts")[0])

        assert keys == {
            "ts",
            "repo",
            "issue",
            "slice_id",
            "verify_round",
            "session",
            "verdict",
            "verdict.ruling",
            "verdict.findings",
            "verdict.findings.rule",
            "verdict.findings.path",
            "verdict.findings.severity",
            "verdict.findings.evidence",
            "verdict.findings.detail",
            "verdict.findings.line",
            "severity_counts",
            "severity_counts.high",
            "severity_counts.medium",
            "severity_counts.low",
            "diff_stats",
            "diff_stats.files_changed",
            "diff_stats.lines_added",
            "diff_stats.lines_deleted",
        }

    def test_the_corpus_diff_keys_are_the_identity_of_the_round_and_the_text_it_judged(self, tmp_path: Path) -> None:
        LocalCorpus(clock=self.frozen_at()).record(CorpusEntryMother.of_the_slice())

        keys = self.flattened(self.rows_of(tmp_path, "diffs")[0])

        assert keys == {
            "ts",
            "repo",
            "issue",
            "slice_id",
            "verify_round",
            "session",
            "diff",
        }

    def test_the_tool_use_keys_cover_a_use_that_touched_a_path_and_one_that_failed(self, tmp_path: Path) -> None:
        log = LocalToolUseLog(clock=self.frozen_at())
        log.record(HarnessCallToolUseMother.of_the_implementer())
        log.record(HarnessCallToolUseMother.of_the_implementer_with_a_failure())

        rows = self.rows_of(tmp_path, "tool-uses")
        keys = self.flattened(rows[0]) | self.flattened(rows[1])

        assert keys == {
            "ts",
            "repo",
            "issue",
            "slice_id",
            "step",
            "session",
            "uses",
            "uses.turn",
            "uses.tool",
            "uses.path",
            "uses.failed",
        }

    def test_the_unrecorded_tool_use_keys_are_the_identity_of_the_call_and_the_cause(self, tmp_path: Path) -> None:
        call = UnrecordedCallToolUse(
            coordinates=HarnessCallToolUseMother.coordinates(),
            step=HarnessCallToolUseMother.of_the_implementer().step,
            session=HarnessCallToolUseMother.SESSION,
            cause=UnrecordedConversationCause.NOT_FOUND,
        )
        LocalToolUseLog(clock=self.frozen_at()).record_unrecorded(call)

        keys = self.flattened(self.rows_of(tmp_path, "unrecorded-tool-uses")[0])

        assert keys == {"ts", "repo", "issue", "slice_id", "step", "session", "cause"}

    def test_the_event_keys_cover_the_spend_it_carries(self, tmp_path: Path) -> None:
        LocalEventLog().emit(EventMother.advancing())

        keys = self.flattened(self.rows_of(tmp_path, "events")[0])

        assert keys == {
            "ts",
            "repo",
            "issue",
            "slice_id",
            "step",
            "spend",
            "spend.cost_usd",
            "spend.turns",
            "spend.duration_ms",
            "spend.calls",
            "spend.models",
            "spend.input_tokens",
            "spend.output_tokens",
            "spend.cache_creation_tokens",
            "spend.cache_read_tokens",
            "spend.ttft_ms",
            "spend.duration_api_ms",
            "status",
        }
