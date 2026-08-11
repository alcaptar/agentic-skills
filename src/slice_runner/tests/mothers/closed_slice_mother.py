from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.closed_slice import ClosedSlice
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.run_state import RunState
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.run_mother import RunMother

if TYPE_CHECKING:
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.discard_cause import DiscardCause
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.run import Run


class ClosedSliceMother:
    REPO: ClassVar[str] = "alcaptar/agentic-skills"
    ISSUE: ClassVar[int] = 38
    SLICE_ID: ClassVar[str] = "slice-07"
    NAME: ClassVar[str] = "controles-como-puerto"
    BUDGETS: ClassVar[Budgets] = Budgets()
    MODELS: ClassVar[RoleModels] = RoleModels(understand="sonnet", implement="sonnet")

    @classmethod
    def merged(cls) -> ClosedSlice:
        return cls._closed(RunState.MERGED)

    @classmethod
    def closed_as(cls, state: RunState) -> ClosedSlice:
        return cls._closed(state)

    @classmethod
    def still_open(cls) -> ClosedSlice:
        return cls._closed(RunState.OPEN)

    @classmethod
    def merged_measuring(cls, *spends: HarnessSpend) -> ClosedSlice:
        return cls._closed(RunState.MERGED, spends=spends)

    @classmethod
    def merged_measuring_nothing(cls) -> ClosedSlice:
        return cls.merged_measuring()

    @classmethod
    def vetoed_over(cls, *findings: Finding) -> ClosedSlice:
        return cls._closed(RunState.BLOCKED_VERIFY, findings=findings)

    @classmethod
    def merged_after_correcting(cls, *findings: Finding) -> ClosedSlice:
        return cls._closed(RunState.MERGED, findings=findings, findings_of_the_last_round=())

    @classmethod
    def merged_after_going_back_for_every_reason(cls) -> ClosedSlice:
        return cls._closed(RunState.MERGED, run=RunMother.that_went_back_for_every_reason())

    @classmethod
    def merged_discarding_because_of(cls, cause: DiscardCause | None) -> ClosedSlice:
        return cls._closed(RunState.MERGED, run=RunMother.that_went_back_for_every_reason(), discard_cause=cause)

    @classmethod
    def merged_leaving_out(cls, *debt: str) -> ClosedSlice:
        return cls._closed(RunState.MERGED, debt=debt)

    @classmethod
    def merged_measuring_the_diff(cls, stats: DiffStats) -> ClosedSlice:
        return cls._closed(RunState.MERGED, diff_stats=stats)

    @classmethod
    def merged_with_config(cls, *, budgets: Budgets | None = None, models: RoleModels | None = None) -> ClosedSlice:
        return cls._closed(RunState.MERGED, budgets=budgets, models=models)

    @classmethod
    def _closed(
        cls,
        state: RunState,
        *,
        run: Run | None = None,
        budgets: Budgets | None = None,
        models: RoleModels | None = None,
        spends: tuple[HarnessSpend, ...] | None = None,
        findings: tuple[Finding, ...] = (),
        findings_of_the_last_round: tuple[Finding, ...] | None = None,
        discard_cause: DiscardCause | None = None,
        debt: tuple[str, ...] = (),
        diff_stats: DiffStats | None = None,
    ) -> ClosedSlice:
        return ClosedSlice(
            repo=cls.REPO,
            issue=cls.ISSUE,
            slice_id=cls.SLICE_ID,
            name=cls.NAME,
            state=state,
            run=run or RunMother.awaiting_merge(),
            budgets=budgets or cls.BUDGETS,
            models=models or cls.MODELS,
            spends=(HarnessSpendMother.of_the_implementer_call(),) if spends is None else spends,
            findings=findings,
            findings_of_the_last_round=findings if findings_of_the_last_round is None else findings_of_the_last_round,
            discard_cause=discard_cause,
            debt=debt,
            diff_stats=diff_stats,
        )
