from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal, NoReturn

from slice_runner.application.actions.catch_up_branch import CatchUpBranchParams
from slice_runner.application.actions.close_parent import CloseParentParams
from slice_runner.application.actions.deliver_slice import DeliverSliceParams
from slice_runner.application.actions.implement_slice import ImplementSliceParams
from slice_runner.application.actions.record_closure import RecordClosureParams
from slice_runner.application.actions.record_step import RecordStepParams
from slice_runner.application.actions.reopen_slice import ReopenSliceParams
from slice_runner.application.actions.run_controls import RunControlsParams
from slice_runner.application.actions.seek_alignment import SeekAlignmentParams
from slice_runner.application.actions.stage_slice import StageSliceParams
from slice_runner.application.actions.verify_slice import VerifySliceParams
from slice_runner.application.queries.read_ci_status import ReadCiStatusParams
from slice_runner.application.queries.read_pull_request_status import ReadPullRequestStatusParams
from slice_runner.application.queries.run_prechecks import RunPrechecksParams
from slice_runner.application.queries.select_slice import SelectSliceParams
from slice_runner.domain.discarded_call import DiscardedCall
from slice_runner.domain.exceptions import (
    DirtyIndexError,
    MeasuredCallError,
    MissingBranchError,
    NoPullRequestError,
    NoSliceLeftError,
)
from slice_runner.domain.halt import Halt
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.precheck_result import PrecheckResult
from slice_runner.domain.prechecks import Prechecks
from slice_runner.domain.pull_request_state import PullRequestState
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.run import Run
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.application.actions.catch_up_branch import CatchUpBranch
    from slice_runner.application.actions.close_parent import CloseParent
    from slice_runner.application.actions.deliver_slice import DeliverSlice
    from slice_runner.application.actions.implement_slice import ImplementSlice
    from slice_runner.application.actions.record_closure import RecordClosure
    from slice_runner.application.actions.record_step import RecordStep
    from slice_runner.application.actions.reopen_slice import ReopenSlice
    from slice_runner.application.actions.run_controls import RunControls
    from slice_runner.application.actions.seek_alignment import SeekAlignment
    from slice_runner.application.actions.stage_slice import StageSlice
    from slice_runner.application.actions.verify_slice import VerifySlice
    from slice_runner.application.queries.read_ci_status import ReadCiStatus
    from slice_runner.application.queries.read_pull_request_status import ReadPullRequestStatus
    from slice_runner.application.queries.run_prechecks import RunPrechecks
    from slice_runner.application.queries.select_slice import SelectSlice, SelectSliceResult
    from slice_runner.domain.branches import Branches
    from slice_runner.domain.budgets import Budgets
    from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.deploy_watch import DeployWatch
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.forum import Forum
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.pull_request_writer import PullRequestWriter
    from slice_runner.domain.reported_path import ReportedPath
    from slice_runner.domain.retry_response import RetryResponse
    from slice_runner.domain.role_models import RoleModels
    from slice_runner.domain.run_repository import RunRepository
    from slice_runner.domain.state_machine import StateMachine
    from slice_runner.domain.sub_issue import SubIssue
    from slice_runner.domain.transition import Transition
    from slice_runner.domain.verdict import Verdict


@dataclass(frozen=True, kw_only=True, slots=True)
class ConductSliceParams:
    repo: str
    issue: int
    worktree: str
    base: str
    logs: Path
    slice_id: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class ConductSliceResult:
    halt: Halt
    state: RunState
    step: Step
    precheck: PrecheckResult | None = None
    pull_request: int | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class ConductSliceProgress:
    params: ConductSliceParams
    chosen: SelectSliceResult
    run: Run
    label: IssueLabel | None
    paths: tuple[ReportedPath, ...] = field(default=())
    debt: tuple[str, ...] = field(default=())
    verdicts: tuple[Verdict, ...] = field(default=())
    spends: tuple[HarnessSpend, ...] = field(default=())
    control_logs: tuple[Path, ...] = field(default=())
    hygiene_refusal: str = ""
    understanding: str = ""
    retry_instruction: str = ""
    pull_request: int | None = None
    waited_seconds: int = 0
    discarded_call: DiscardedCall | None = None
    ci_indeterminate_cause: CiIndeterminateCause | None = None
    diff_stats: DiffStats | None = None
    conflicting_paths: tuple[str, ...] = field(default=())

    @property
    def spend(self) -> HarnessSpend:
        return HarnessSpend.summing(self.spends)

    @property
    def findings_of_the_last_round(self) -> tuple[Finding, ...]:
        return self.verdicts[-1].findings if self.verdicts else ()

    @property
    def findings_of_every_round(self) -> tuple[Finding, ...]:
        return tuple(finding for verdict in self.verdicts for finding in verdict.findings)

    @property
    def subissue(self) -> SubIssue:
        return self.chosen.subissue

    @property
    def parent(self) -> ParentIssue:
        return self.chosen.parent


@dataclass(frozen=True, kw_only=True, slots=True)
class SteppedSlice:
    progress: ConductSliceProgress
    outcome: Outcome
    call_died: bool = False
    verdict_recorded: bool = False


@dataclass(frozen=True, kw_only=True, slots=True)
class HaltedSlice:
    progress: ConductSliceProgress
    halt: Halt


@dataclass(frozen=True, kw_only=True, slots=True)
class ConductSliceUseCases:
    select: SelectSlice
    reopen: ReopenSlice
    prechecks: RunPrechecks
    implement: ImplementSlice
    stage: StageSlice
    run_controls: RunControls
    verify: VerifySlice
    deliver: DeliverSlice
    close: CloseParent
    record_step: RecordStep
    record_closure: RecordClosure
    read_ci: ReadCiStatus
    read_pull_request: ReadPullRequestStatus
    seek_alignment: SeekAlignment
    catch_up: CatchUpBranch


@dataclass(frozen=True, kw_only=True, slots=True)
class ConductSlicePorts:
    repository: RunRepository
    branches: Branches
    forum: Forum
    clock: Clock
    pull_request: PullRequestWriter
    deploy_watch: DeployWatch


class ConductSlice:
    def __init__(
        self,
        *,
        use_cases: ConductSliceUseCases,
        ports: ConductSlicePorts,
        machine: StateMachine,
        budgets: Budgets,
        models: RoleModels,
    ) -> None:
        self._select = use_cases.select
        self._reopen = use_cases.reopen
        self._prechecks = use_cases.prechecks
        self._implement = use_cases.implement
        self._stage = use_cases.stage
        self._run_controls = use_cases.run_controls
        self._verify = use_cases.verify
        self._deliver = use_cases.deliver
        self._close = use_cases.close
        self._record_step = use_cases.record_step
        self._record_closure = use_cases.record_closure
        self._read_ci = use_cases.read_ci
        self._read_pull_request = use_cases.read_pull_request
        self._seek_alignment = use_cases.seek_alignment
        self._catch_up = use_cases.catch_up
        self._repository = ports.repository
        self._branches = ports.branches
        self._forum = ports.forum
        self._clock = ports.clock
        self._pull_request = ports.pull_request
        self._deploy_watch = ports.deploy_watch
        self._machine = machine
        self._budgets = budgets
        self._models = models

    def execute(self, params: ConductSliceParams) -> ConductSliceResult:
        try:
            chosen = self._select.execute(
                SelectSliceParams(repo=params.repo, issue=params.issue, slice_id=params.slice_id)
            )
        except NoSliceLeftError as unselectable:
            reconciled = sum(
                self._closing_a_merge_missed_between_invocations(params, dangling) for dangling in unselectable.dangling
            )
            for subissue, response in unselectable.malformed_retries:
                if response.reason is not None:
                    self._repository.write_malformed_response(
                        repo=params.repo, issue=subissue.number, reason=response.reason
                    )
            raise self._reported_after_reconciling(unselectable, reconciled) from unselectable

        for dangling in chosen.dangling:
            self._closing_a_merge_missed_between_invocations(params, dangling)
        retry = chosen.retry
        if retry is not None:
            chosen = self._reopened(params, chosen, retry=retry)
        run = chosen.subissue.run or Run(step=Step.IMPLEMENT)
        progress = ConductSliceProgress(
            params=params,
            chosen=chosen,
            run=run,
            label=chosen.subissue.label,
            spends=(run.spend,) if run.spend.measured else (),
            retry_instruction=retry.instruction if retry is not None else "",
        )
        of_the_subissue = Prechecks.of_the_subissue(chosen.subissue)
        if of_the_subissue is not PrecheckOutcome.CLEAR:
            return self._ending(progress, Halt.PRECHECKS_BLOCKED, precheck=PrecheckResult(outcome=of_the_subissue))
        if chosen.subissue.run is not None:
            return self._resuming(progress)
        if chosen.subissue.label is IssueLabel.AWAITING_ALIGNMENT:
            return self._conducting(replace(progress, run=replace(progress.run, step=Step.UNDERSTAND)))

        return self._aligning(progress)

    def _resuming(self, progress: ConductSliceProgress) -> ConductSliceResult:
        if self._branch_still_standing(progress):
            if self._already_delivered(progress.run.step):
                return self._conducting(progress)

            return self._caught_up_before_conducting(progress)
        if progress.run.step is Step.UNDERSTAND:
            if progress.run.understanding_pending:
                return self._aligning(progress)

            return self._recreating_the_branch(progress)

        self._missing_branch(progress)

    @staticmethod
    def _already_delivered(step: Step) -> bool:
        return step is Step.AWAIT_CI or step is Step.AWAIT_MERGE

    def _caught_up_before_conducting(self, progress: ConductSliceProgress) -> ConductSliceResult:
        caught_up = self._catch_up.execute(
            CatchUpBranchParams(
                worktree=progress.params.worktree, branch=progress.subissue.branch, base=progress.params.base
            )
        )
        if caught_up.outcome is Outcome.CONFLICTING:
            return self._blocked_by_a_catch_up_conflict(
                replace(progress, conflicting_paths=caught_up.conflicting_paths)
            )

        return self._conducting(progress)

    def _blocked_by_a_catch_up_conflict(self, progress: ConductSliceProgress) -> ConductSliceResult:
        transition = self._machine.after(progress.run, Outcome.CONFLICTING)
        closed = self._recorded(progress, transition)

        return self._closing(closed, transition.state)

    def _recreating_the_branch(self, progress: ConductSliceProgress) -> ConductSliceResult:
        self._branches.create(
            worktree=progress.params.worktree, name=progress.subissue.branch, base=progress.params.base
        )

        return self._conducting(progress)

    def _reopened(
        self, params: ConductSliceParams, chosen: SelectSliceResult, *, retry: RetryResponse
    ) -> SelectSliceResult:
        reopened = self._reopen.execute(
            ReopenSliceParams(repo=params.repo, subissue=chosen.subissue, instruction=retry.instruction)
        )

        return replace(chosen, subissue=reopened.subissue)

    def _branch_still_standing(self, progress: ConductSliceProgress) -> bool:
        return self._branches.exists(worktree=progress.params.worktree, name=progress.subissue.branch)

    @staticmethod
    def _missing_branch(progress: ConductSliceProgress) -> NoReturn:
        raise MissingBranchError(
            f"the run of {progress.subissue.slice_id.canonical} stands on `{progress.run.step}` and resumes "
            f"expecting the branch `{progress.subissue.branch}` to exist: the worktree has no such branch"
        )

    def _aligning(self, progress: ConductSliceProgress) -> ConductSliceResult:
        precheck = self._prechecks.execute(
            RunPrechecksParams(
                repo=progress.params.repo,
                worktree=progress.params.worktree,
                branch=progress.subissue.branch,
                base=progress.params.base,
                subissue=progress.subissue,
                parent=progress.parent,
            )
        )
        if precheck.outcome is not PrecheckOutcome.CLEAR:
            if precheck.reason is not None:
                self._repository.write_precheck_reason(
                    repo=progress.params.repo,
                    issue=progress.subissue.number,
                    outcome=precheck.outcome,
                    reason=precheck.reason,
                )

            return self._ending(progress, Halt.PRECHECKS_BLOCKED, precheck=precheck)

        marked = self._marked_in_progress(progress)

        return self._conducting(
            replace(marked, run=replace(marked.run, step=Step.UNDERSTAND, understanding_pending=True))
        )

    def _marked_in_progress(self, progress: ConductSliceProgress) -> ConductSliceProgress:
        if progress.label is IssueLabel.IN_PROGRESS:
            return progress

        self._repository.write_label(
            repo=progress.params.repo, issue=progress.subissue.number, remove=progress.label, add=IssueLabel.IN_PROGRESS
        )

        return replace(progress, label=IssueLabel.IN_PROGRESS)

    def _awaiting_alignment(self, progress: ConductSliceProgress) -> SteppedSlice:
        try:
            sought = self._seek_alignment.execute(
                SeekAlignmentParams(
                    repo=progress.params.repo,
                    worktree=progress.params.worktree,
                    subissue=progress.subissue,
                    parent=progress.parent,
                    run=progress.run,
                    understanding=progress.understanding,
                )
            )
        except MeasuredCallError as rejection:
            discarded = self._discarding(progress, rejection)

            return self._within_budget(
                SteppedSlice(progress=discarded, outcome=Outcome.DISCARDED), call=rejection.spend
            )

        updated = replace(
            progress,
            run=sought.run,
            understanding=sought.understanding,
            spends=(*progress.spends, sought.spend) if sought.spend is not None else progress.spends,
        )
        response = sought.response
        if response is None:
            return self._paused_for_alignment(updated)

        return SteppedSlice(progress=updated, outcome=Outcome.of_the_alignment(response))

    def _paused_for_alignment(self, progress: ConductSliceProgress) -> SteppedSlice:
        self._repository.pause_for_alignment(
            repo=progress.params.repo, issue=progress.subissue.number, remove=progress.label
        )
        self._branches.create(
            worktree=progress.params.worktree, name=progress.subissue.branch, base=progress.params.base
        )

        return SteppedSlice(
            progress=replace(progress, label=IssueLabel.AWAITING_ALIGNMENT),
            outcome=Outcome.PENDING,
        )

    def _seeded(self, progress: ConductSliceProgress) -> ConductSliceProgress:
        if progress.understanding:
            return progress

        agreed = self._repository.read_understanding(repo=progress.params.repo, issue=progress.subissue.number)

        return replace(progress, understanding=agreed)

    def _conducting(self, progress: ConductSliceProgress) -> ConductSliceResult:
        while True:
            stepped = self._stepping(progress)
            if isinstance(stepped, HaltedSlice):
                return self._ending(stepped.progress, stepped.halt)
            transition = self._machine.after(
                stepped.progress.run,
                stepped.outcome,
                call_died=stepped.call_died,
                verdict_recorded=stepped.verdict_recorded,
            )
            progress = self._recorded(stepped.progress, transition)
            if transition.state is not RunState.OPEN:
                return self._closing(progress, transition.state)
            if transition.wait_seconds > 0:
                progress = self._waiting(progress, transition.wait_seconds)
                if self._budgets.wait_exhausted(progress.waited_seconds, step=progress.run.step):
                    return self._exhausted(progress)

    def _exhausted(self, progress: ConductSliceProgress) -> ConductSliceResult:
        if progress.run.step is Step.AWAIT_MERGE:
            self._repository.flag_unmerged_pull_request(
                repo=progress.params.repo, issue=progress.subissue.number, pull_request=self._pull_request_of(progress)
            )

        return self._ending(progress, Halt.WAIT_EXHAUSTED)

    def _stepping(self, progress: ConductSliceProgress) -> SteppedSlice | HaltedSlice:
        match progress.run.step:
            case Step.UNDERSTAND | Step.IMPLEMENT | Step.RUN_CONTROLS | Step.VERIFY:
                return self._stepping_while_producing(progress, progress.run.step)
            case Step.OPEN_PULL_REQUEST | Step.AWAIT_CI | Step.CATCH_UP | Step.AWAIT_MERGE:
                return self._stepping_while_delivering(progress, progress.run.step)

    def _stepping_while_producing(
        self,
        progress: ConductSliceProgress,
        step: Literal[Step.UNDERSTAND, Step.IMPLEMENT, Step.RUN_CONTROLS, Step.VERIFY],
    ) -> SteppedSlice:
        match step:
            case Step.UNDERSTAND:
                return self._awaiting_alignment(progress)
            case Step.IMPLEMENT:
                return self._implementing(progress)
            case Step.RUN_CONTROLS:
                return self._running_the_controls(progress)
            case Step.VERIFY:
                return self._judging(progress)

    def _stepping_while_delivering(
        self,
        progress: ConductSliceProgress,
        step: Literal[Step.OPEN_PULL_REQUEST, Step.AWAIT_CI, Step.CATCH_UP, Step.AWAIT_MERGE],
    ) -> SteppedSlice | HaltedSlice:
        match step:
            case Step.OPEN_PULL_REQUEST:
                return self._opening_the_pull_request(progress)
            case Step.AWAIT_CI:
                return self._asking_the_ci(progress)
            case Step.CATCH_UP:
                return self._catching_up_the_branch(progress)
            case Step.AWAIT_MERGE:
                return self._asking_for_the_merge(progress)

    def _catching_up_the_branch(self, progress: ConductSliceProgress) -> SteppedSlice:
        caught_up = self._catch_up.execute(
            CatchUpBranchParams(
                worktree=progress.params.worktree, branch=progress.subissue.branch, base=progress.params.base
            )
        )
        if caught_up.outcome is not Outcome.CONFLICTING:
            return SteppedSlice(progress=progress, outcome=caught_up.outcome)

        return SteppedSlice(
            progress=replace(progress, conflicting_paths=caught_up.conflicting_paths), outcome=caught_up.outcome
        )

    def _implementing(self, progress: ConductSliceProgress) -> SteppedSlice:
        if self._budgets.exhausted(progress.spend):
            return SteppedSlice(progress=progress, outcome=Outcome.OVER_BUDGET)

        progress = self._seeded(progress)

        try:
            implementation = self._implement.execute(
                ImplementSliceParams(
                    repo=progress.params.repo,
                    worktree=progress.params.worktree,
                    subissue=progress.subissue,
                    parent=progress.parent,
                    findings=progress.findings_of_the_last_round,
                    control_logs=progress.control_logs,
                    hygiene_refusal=progress.hygiene_refusal,
                    understanding=progress.understanding,
                    retry_instruction=progress.retry_instruction,
                    requested_changes=progress.run.requested_changes,
                    previous_call_died=progress.run.previous_call_died,
                )
            )
        except MeasuredCallError as rejection:
            discarded = self._discarding(progress, rejection)

            return self._within_budget(
                SteppedSlice(progress=discarded, outcome=Outcome.DISCARDED, call_died=True), call=rejection.spend
            )

        implemented = replace(
            progress,
            paths=implementation.paths,
            debt=implementation.left_out,
            spends=(*progress.spends, implementation.spend),
        )

        return self._within_budget(SteppedSlice(progress=implemented, outcome=Outcome.DONE), call=implementation.spend)

    def _running_the_controls(self, progress: ConductSliceProgress) -> SteppedSlice:
        try:
            self._stage.execute(StageSliceParams(worktree=progress.params.worktree, paths=progress.paths))
        except DirtyIndexError as refusal:
            return SteppedSlice(
                progress=replace(progress, control_logs=(), hygiene_refusal=str(refusal)),
                outcome=Outcome.HYGIENE_REJECTED,
            )

        round_progress = replace(progress, hygiene_refusal="")
        ran = self._run_controls.execute(
            RunControlsParams(
                worktree=round_progress.params.worktree,
                controls=round_progress.parent.controls,
                logs=round_progress.params.logs,
                slice_id=round_progress.subissue.slice_id,
                control_rounds_logged=round_progress.run.control_rounds_logged,
            )
        )

        return SteppedSlice(progress=replace(round_progress, control_logs=ran.red_logs), outcome=ran.outcome)

    def _judging(self, progress: ConductSliceProgress) -> SteppedSlice:
        if self._budgets.exhausted(progress.spend):
            return SteppedSlice(progress=progress, outcome=Outcome.OVER_BUDGET)

        try:
            verification = self._verify.execute(
                VerifySliceParams(
                    repo=progress.params.repo,
                    issue=progress.subissue.number,
                    worktree=progress.params.worktree,
                    base=f"origin/{progress.params.base}",
                    slice_id=progress.subissue.slice_id.canonical,
                    verify_round=progress.run.verify_round_in_progress,
                    prior_art=progress.parent.prior_art,
                    signal=progress.subissue.signal,
                    excludes=progress.subissue.excludes,
                    replaces=progress.subissue.replaces,
                    criteria=progress.subissue.criteria,
                    sources=progress.parent.sources,
                    checklist=progress.chosen.checklist,
                )
            )
        except MeasuredCallError as rejection:
            discarded = self._discarding(progress, rejection)

            return self._within_budget(
                SteppedSlice(progress=discarded, outcome=Outcome.DISCARDED), call=rejection.spend
            )

        judged = replace(
            progress,
            spends=(*progress.spends, verification.spend),
            verdicts=(*progress.verdicts, verification.verdict),
            diff_stats=verification.diff_stats,
        )
        stepped = SteppedSlice(
            progress=judged, outcome=Outcome.of_the_verdict(verification.verdict), verdict_recorded=True
        )
        if verification.verdict.ruling is Ruling.PASS:
            return stepped

        return self._within_budget(stepped, call=verification.spend)

    def _within_budget(self, stepped: SteppedSlice, *, call: HarnessSpend | None) -> SteppedSlice:
        exhaustion = self._budgets.cost_exhausted(call=call, total=stepped.progress.spend)

        return replace(stepped, outcome=Outcome.of_the_cost_exhaustion(exhaustion, otherwise=stepped.outcome))

    @staticmethod
    def _discarding(progress: ConductSliceProgress, rejection: MeasuredCallError) -> ConductSliceProgress:
        spends = progress.spends if rejection.spend is None else (*progress.spends, rejection.spend)

        return replace(
            progress, spends=spends, discarded_call=DiscardedCall.of_the_rejection(progress.run.step, rejection)
        )

    def _opening_the_pull_request(self, progress: ConductSliceProgress) -> SteppedSlice:
        opened = self._deliver.execute(
            DeliverSliceParams(
                worktree=progress.params.worktree,
                repo=progress.params.repo,
                branch=progress.subissue.branch,
                base=progress.params.base,
                title=self._pull_request.title(progress.subissue),
                commit_message=self._pull_request.commit_message(progress.subissue),
                body=self._pull_request.body(
                    progress.subissue, debt=progress.debt, findings=progress.findings_of_the_last_round
                ),
                from_catch_up=progress.run.catching_up_the_branch,
            )
        )

        return SteppedSlice(progress=replace(progress, pull_request=opened), outcome=Outcome.DONE)

    def _asking_the_ci(self, progress: ConductSliceProgress) -> SteppedSlice:
        opened = self._pull_request_of(progress)
        result = self._read_ci.execute(ReadCiStatusParams(repo=progress.params.repo, pull_request=opened))
        asked = replace(progress, pull_request=opened)
        if result.outcome is not Outcome.INDETERMINATE:
            return SteppedSlice(progress=asked, outcome=result.outcome)

        return SteppedSlice(
            progress=replace(asked, ci_indeterminate_cause=result.indeterminate_cause), outcome=result.outcome
        )

    def _asking_for_the_merge(self, progress: ConductSliceProgress) -> SteppedSlice | HaltedSlice:
        opened = self._pull_request_of(progress)
        asked = replace(progress, pull_request=opened)
        result = self._read_pull_request.execute(
            ReadPullRequestStatusParams(
                repo=progress.params.repo, pull_request=opened, last_reviewed_id=progress.run.last_reviewed_id
            )
        )

        match result.state:
            case PullRequestState.MERGED:
                return SteppedSlice(progress=asked, outcome=Outcome.DONE)
            case PullRequestState.OPEN:
                if not result.requested_changes:
                    return SteppedSlice(progress=asked, outcome=Outcome.PENDING)

                run = replace(
                    asked.run, last_reviewed_id=result.last_reviewed_id, requested_changes=result.requested_changes
                )

                return SteppedSlice(progress=replace(asked, run=run), outcome=Outcome.CHANGES_REQUESTED)
            case PullRequestState.CLOSED:
                return HaltedSlice(progress=asked, halt=Halt.PULL_REQUEST_CLOSED)

    def _pull_request_of(self, progress: ConductSliceProgress) -> int:
        if progress.pull_request is not None:
            return progress.pull_request

        opened = self._forum.any_pull_request(repo=progress.params.repo, branch=progress.subissue.branch)
        if opened is None:
            raise NoPullRequestError(
                f"the run of {progress.subissue.slice_id.canonical} stands on `{progress.run.step}` and no pull "
                f"request of any state was found for {progress.subissue.branch}"
            )

        return opened

    def _recorded(self, progress: ConductSliceProgress, transition: Transition) -> ConductSliceProgress:
        recorded = self._record_step.execute(
            RecordStepParams(
                repo=progress.params.repo,
                issue=progress.subissue.number,
                slice_id=progress.subissue.slice_id.canonical,
                current=progress.run,
                label=progress.label,
                transition=transition,
                spend=progress.spend,
            )
        )

        return replace(
            progress,
            run=recorded.run,
            label=recorded.label,
            waited_seconds=self._carried(progress, stepped_to=recorded.run.step),
        )

    @staticmethod
    def _carried(progress: ConductSliceProgress, *, stepped_to: Step) -> int:
        if stepped_to is progress.run.step:
            return progress.waited_seconds

        return 0

    def _closing_a_merge_missed_between_invocations(self, params: ConductSliceParams, subissue: SubIssue) -> bool:
        run = subissue.run
        if run is None:
            return False

        opened = self._forum.any_pull_request(repo=params.repo, branch=subissue.branch)
        if (
            opened is None
            or self._forum.pull_request_state(repo=params.repo, number=opened).state is not PullRequestState.MERGED
        ):
            return False

        self._record_closure.execute(
            RecordClosureParams(
                repo=params.repo,
                issue=subissue.number,
                slice_id=subissue.slice_id.canonical,
                name=subissue.slice_id.name,
                state=RunState.MERGED,
                run=run,
                budgets=self._budgets,
                models=self._models,
            )
        )
        label = subissue.label
        if label is not None:
            self._repository.remove_label(repo=params.repo, issue=subissue.number, remove=label)
        self._repository.clear_run(repo=params.repo, issue=subissue.number)
        self._close.execute(CloseParentParams(repo=params.repo, issue=params.issue))

        return True

    @staticmethod
    def _reported_after_reconciling(unselectable: NoSliceLeftError, reconciled: int) -> NoSliceLeftError:
        error = NoSliceLeftError(f"{unselectable}; reconciled {reconciled} dangling slice(s) before giving up")
        error.dangling = unselectable.dangling
        error.malformed_retries = unselectable.malformed_retries

        return error

    def _waiting(self, progress: ConductSliceProgress, seconds: int) -> ConductSliceProgress:
        self._clock.sleep(seconds=seconds)

        return replace(progress, waited_seconds=progress.waited_seconds + seconds)

    def _closing(self, progress: ConductSliceProgress, state: RunState) -> ConductSliceResult:
        self._record_closure.execute(
            RecordClosureParams(
                repo=progress.params.repo,
                issue=progress.subissue.number,
                slice_id=progress.subissue.slice_id.canonical,
                name=progress.subissue.slice_id.name,
                state=state,
                run=progress.run,
                budgets=self._budgets,
                models=self._models,
                findings=progress.findings_of_every_round,
                findings_of_the_last_round=progress.findings_of_the_last_round,
                discarded_call=progress.discarded_call,
                ci_indeterminate_cause=progress.ci_indeterminate_cause,
                debt=progress.debt,
                diff_stats=progress.diff_stats,
                conflicting_paths=progress.conflicting_paths,
            )
        )
        if state is RunState.MERGED:
            self._repository.clear_run(repo=progress.params.repo, issue=progress.subissue.number)
            self._close.execute(CloseParentParams(repo=progress.params.repo, issue=progress.params.issue))
            if not progress.subissue.signal_is_exempt:
                self._deploy_watch.watch(
                    worktree=progress.params.worktree, repo=progress.params.repo, signal=progress.subissue.signal
                )

        return self._ending(progress, Halt.RUN_CLOSED, state=state)

    @staticmethod
    def _ending(
        progress: ConductSliceProgress,
        halt: Halt,
        *,
        state: RunState = RunState.OPEN,
        precheck: PrecheckResult | None = None,
    ) -> ConductSliceResult:
        return ConductSliceResult(
            halt=halt,
            state=state,
            step=progress.run.step,
            precheck=precheck,
            pull_request=progress.pull_request,
        )
