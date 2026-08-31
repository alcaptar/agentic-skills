from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.closed_slice import ClosedSlice
from slice_runner.domain.declared_debt import DeclaredDebt
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.run_state import RunState
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.run_mother import RunMother

if TYPE_CHECKING:
    from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.discarded_call import DiscardedCall
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.run import Run


class ClosedSliceMother:
    REPO: ClassVar[str] = "alcaptar/agentic-skills"
    ISSUE: ClassVar[int] = 38
    SLICE_ID: ClassVar[str] = "slice-07"
    NAME: ClassVar[str] = "controles-como-puerto"
    BUDGETS: ClassVar[Budgets] = Budgets()
    MODELS: ClassVar[RoleModels] = RoleModels(understand="sonnet", implement="sonnet", verify="sonnet")

    @classmethod
    def merged(cls) -> ClosedSlice:
        return cls._closed(RunState.MERGED)

    @classmethod
    def closed_as(cls, state: RunState) -> ClosedSlice:
        return cls._closed(state)

    @classmethod
    def merged_for_issue(cls, issue: int) -> ClosedSlice:
        return cls._closed(RunState.MERGED, issue=issue)

    @classmethod
    def closed_as_for_issue(cls, state: RunState, *, issue: int) -> ClosedSlice:
        return cls._closed(state, issue=issue)

    @classmethod
    def merged_with_a_user_story_key(cls) -> ClosedSlice:
        return cls._closed(RunState.MERGED, slice_id="PROJ-1234-07")

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
    def merged_discarding_because_of(cls, discarded: DiscardedCall | None) -> ClosedSlice:
        return cls._closed(RunState.MERGED, run=RunMother.that_went_back_for_every_reason(), discarded_call=discarded)

    @classmethod
    def blocked_indeterminate_because_of(cls, cause: CiIndeterminateCause | None) -> ClosedSlice:
        return cls._closed(RunState.BLOCKED_CI_INDETERMINATE, ci_indeterminate_cause=cause)

    @classmethod
    def merged_leaving_out(cls, *left_out: str) -> ClosedSlice:
        return cls._closed(RunState.MERGED, debt=DeclaredDebt(declared=True, left_out=left_out))

    @classmethod
    def merged_declaring_nothing_left_out(cls) -> ClosedSlice:
        return cls._closed(RunState.MERGED, debt=DeclaredDebt(declared=True, left_out=()))

    @classmethod
    def merged_measuring_the_diff(cls, stats: DiffStats) -> ClosedSlice:
        return cls._closed(RunState.MERGED, diff_stats=stats)

    @classmethod
    def merged_measuring_the_diff_and_spend(cls, stats: DiffStats, *spends: HarnessSpend) -> ClosedSlice:
        return cls._closed(RunState.MERGED, diff_stats=stats, spends=spends)

    @classmethod
    def merged_discarding_and_measuring_the_diff(cls, discarded: DiscardedCall, stats: DiffStats) -> ClosedSlice:
        return cls._closed(RunState.MERGED, discarded_call=discarded, diff_stats=stats)

    @classmethod
    def merged_with_config(cls, *, budgets: Budgets | None = None, models: RoleModels | None = None) -> ClosedSlice:
        return cls._closed(RunState.MERGED, budgets=budgets, models=models)

    @classmethod
    def merged_after_retrying_controls_and_ci(cls, *, control_retries: int, ci_retries: int) -> ClosedSlice:
        return cls._closed(
            RunState.MERGED,
            run=RunMother.merged_after_retrying_controls_and_ci(control_retries=control_retries, ci_retries=ci_retries),
        )

    @classmethod
    def aborted_over_budget(cls, budgets: Budgets, *, spend: HarnessSpend | None = None) -> ClosedSlice:
        return cls._closed(RunState.ABORTED_BUDGET, budgets=budgets, spends=None if spend is None else (spend,))

    @classmethod
    def _closed(
        cls,
        state: RunState,
        *,
        issue: int | None = None,
        slice_id: str | None = None,
        run: Run | None = None,
        budgets: Budgets | None = None,
        models: RoleModels | None = None,
        spends: tuple[HarnessSpend, ...] | None = None,
        findings: tuple[Finding, ...] = (),
        findings_of_the_last_round: tuple[Finding, ...] | None = None,
        discarded_call: DiscardedCall | None = None,
        ci_indeterminate_cause: CiIndeterminateCause | None = None,
        debt: DeclaredDebt | None = None,
        diff_stats: DiffStats | None = None,
    ) -> ClosedSlice:
        return ClosedSlice(
            repo=cls.REPO,
            issue=cls.ISSUE if issue is None else issue,
            slice_id=cls.SLICE_ID if slice_id is None else slice_id,
            name=cls.NAME,
            state=state,
            run=run or RunMother.awaiting_merge(),
            budgets=budgets or cls.BUDGETS,
            models=models or cls.MODELS,
            spends=(HarnessSpendMother.of_the_implementer_call(),) if spends is None else spends,
            findings=findings,
            findings_of_the_last_round=findings if findings_of_the_last_round is None else findings_of_the_last_round,
            discarded_call=discarded_call,
            ci_indeterminate_cause=ci_indeterminate_cause,
            debt=debt or DeclaredDebt.nothing(),
            diff_stats=diff_stats,
        )
