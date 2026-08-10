from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal

from slice_runner.application.actions.close_parent import CloseParentParams
from slice_runner.application.actions.deliver_slice import DeliverSliceParams
from slice_runner.application.actions.implement_slice import ImplementSliceParams
from slice_runner.application.actions.stage_slice import StageSliceParams
from slice_runner.application.actions.verify_slice import VerifySliceParams
from slice_runner.application.queries.run_prechecks import RunPrechecksParams
from slice_runner.application.queries.select_slice import SelectSliceParams
from slice_runner.domain.alignment import Alignment
from slice_runner.domain.alignment_response_kind import AlignmentResponseKind
from slice_runner.domain.closed_slice import ClosedSlice
from slice_runner.domain.control_status import ControlStatus
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.event import Event
from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.exceptions import (
    DirtyIndexError,
    MeasuredCallError,
    NoPullRequestError,
    NoSliceLeftError,
)
from slice_runner.domain.halt import Halt
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.prechecks import Prechecks
from slice_runner.domain.pull_request_state import PullRequestState
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.run import Run
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.application.actions.close_parent import CloseParent
    from slice_runner.application.actions.deliver_slice import DeliverSlice
    from slice_runner.application.actions.implement_slice import ImplementSlice
    from slice_runner.application.actions.stage_slice import StageSlice
    from slice_runner.application.actions.verify_slice import VerifySlice
    from slice_runner.application.queries.run_prechecks import RunPrechecks
    from slice_runner.application.queries.select_slice import SelectSlice, SelectSliceResult
    from slice_runner.domain.branches import Branches
    from slice_runner.domain.budgets import Budgets
    from slice_runner.domain.ci import Ci
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.control_outcome import ControlOutcome
    from slice_runner.domain.control_runner import ControlRunner
    from slice_runner.domain.deploy_watch import DeployWatch
    from slice_runner.domain.event_log import EventLog
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.forum import Forum
    from slice_runner.domain.metrics_log import MetricsLog
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.pull_request_writer import PullRequestWriter
    from slice_runner.domain.reported_path import ReportedPath
    from slice_runner.domain.run_repository import RunRepository
    from slice_runner.domain.state_machine import StateMachine
    from slice_runner.domain.sub_issue import SubIssue
    from slice_runner.domain.transition import Transition
    from slice_runner.domain.understanding_writer import UnderstandingWriter
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
    precheck: PrecheckOutcome | None = None
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
    control_rounds: int = 0
    hygiene_refusal: str = ""
    understanding: str = ""
    pull_request: int | None = None
    waited_seconds: int = 0
    discard_cause: DiscardCause | None = None

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


@dataclass(frozen=True, kw_only=True, slots=True)
class HaltedSlice:
    progress: ConductSliceProgress
    halt: Halt


@dataclass(frozen=True, kw_only=True, slots=True)
class ConductSliceUseCases:
    select: SelectSlice
    prechecks: RunPrechecks
    implement: ImplementSlice
    stage: StageSlice
    verify: VerifySlice
    deliver: DeliverSlice
    close: CloseParent


@dataclass(frozen=True, kw_only=True, slots=True)
class ConductSlicePorts:
    repository: RunRepository
    branches: Branches
    controls: ControlRunner
    ci: Ci
    forum: Forum
    clock: Clock
    metrics: MetricsLog
    understanding: UnderstandingWriter
    pull_request: PullRequestWriter
    deploy_watch: DeployWatch
    events: EventLog


class ConductSlice:
    def __init__(
        self,
        *,
        use_cases: ConductSliceUseCases,
        ports: ConductSlicePorts,
        machine: StateMachine,
        budgets: Budgets,
    ) -> None:
        self._select = use_cases.select
        self._prechecks = use_cases.prechecks
        self._implement = use_cases.implement
        self._stage = use_cases.stage
        self._verify = use_cases.verify
        self._deliver = use_cases.deliver
        self._close = use_cases.close
        self._repository = ports.repository
        self._branches = ports.branches
        self._controls = ports.controls
        self._ci = ports.ci
        self._forum = ports.forum
        self._clock = ports.clock
        self._metrics = ports.metrics
        self._understanding = ports.understanding
        self._pull_request = ports.pull_request
        self._deploy_watch = ports.deploy_watch
        self._events = ports.events
        self._machine = machine
        self._budgets = budgets

    def execute(self, params: ConductSliceParams) -> ConductSliceResult:
        try:
            chosen = self._select.execute(
                SelectSliceParams(repo=params.repo, issue=params.issue, slice_id=params.slice_id)
            )
        except NoSliceLeftError as unselectable:
            for dangling in unselectable.dangling:
                self._closing_a_merge_missed_between_invocations(params, dangling)
            raise

        for dangling in chosen.dangling:
            self._closing_a_merge_missed_between_invocations(params, dangling)
        run = chosen.subissue.run or Run(step=Step.IMPLEMENT)
        progress = ConductSliceProgress(
            params=params,
            chosen=chosen,
            run=run,
            label=chosen.subissue.label,
            spends=(run.spend,) if run.spend.measured else (),
        )
        of_the_subissue = Prechecks.of_the_subissue(chosen.subissue)
        if of_the_subissue is not PrecheckOutcome.CLEAR:
            return self._ending(progress, Halt.PRECHECKS_BLOCKED, precheck=of_the_subissue)
        if chosen.subissue.run is not None:
            return self._conducting(progress)
        if chosen.subissue.label is IssueLabel.AWAITING_ALIGNMENT:
            return self._conducting(replace(progress, run=replace(progress.run, step=Step.UNDERSTAND)))

        return self._aligning(progress)

    def _aligning(self, progress: ConductSliceProgress) -> ConductSliceResult:
        precheck = self._prechecks.execute(
            RunPrechecksParams(
                repo=progress.params.repo,
                worktree=progress.params.worktree,
                branch=progress.subissue.branch,
                subissue=progress.subissue,
                parent=progress.parent,
            )
        )
        if precheck is not PrecheckOutcome.CLEAR:
            return self._ending(progress, Halt.PRECHECKS_BLOCKED, precheck=precheck)

        marked = self._marked_in_progress(progress)
        published = self._publishing_the_understanding(marked, correction="")
        self._repository.pause_for_alignment(
            repo=progress.params.repo, issue=progress.subissue.number, remove=published.label
        )
        self._branches.create(
            worktree=progress.params.worktree, name=progress.subissue.branch, base=progress.params.base
        )

        return self._conducting(replace(published, label=IssueLabel.AWAITING_ALIGNMENT))

    def _marked_in_progress(self, progress: ConductSliceProgress) -> ConductSliceProgress:
        if progress.label is IssueLabel.IN_PROGRESS:
            return progress

        self._repository.write_label(
            repo=progress.params.repo, issue=progress.subissue.number, remove=progress.label, add=IssueLabel.IN_PROGRESS
        )

        return replace(progress, label=IssueLabel.IN_PROGRESS)

    def _awaiting_alignment(self, progress: ConductSliceProgress) -> SteppedSlice:
        response = self._repository.read_alignment_response(repo=progress.params.repo, issue=progress.subissue.number)
        if response.kind is AlignmentResponseKind.REVIEW:
            progress = self._publishing_the_understanding(self._seeded(progress), correction=response.correction)

        return SteppedSlice(progress=progress, outcome=Outcome.of_the_alignment(response.kind))

    def _publishing_the_understanding(self, progress: ConductSliceProgress, *, correction: str) -> ConductSliceProgress:
        understanding = self._understanding.write(
            subissue=progress.subissue,
            parent=progress.parent,
            repo=progress.params.repo,
            worktree=progress.params.worktree,
            alignment=Alignment(agreed=progress.understanding, correction=correction),
        )
        published = replace(progress, spends=(*progress.spends, understanding.spend), understanding=understanding.text)
        run = replace(published.run, step=Step.UNDERSTAND, spend=published.spend)
        self._writing(published, run=run)
        self._repository.write_understanding(
            repo=progress.params.repo, issue=progress.subissue.number, understanding=understanding.text
        )

        return replace(published, run=run)

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
            transition = self._machine.after(stepped.progress.run, stepped.outcome)
            progress = self._persisted(stepped.progress, transition)
            self._reporting(progress, transition)
            if transition.state is not RunState.OPEN:
                return self._closing(progress, transition.state)
            if transition.wait_seconds > 0:
                progress = self._waiting(progress, transition.wait_seconds)
                if self._budgets.wait_exhausted(progress.waited_seconds):
                    return self._exhausted(progress)

    def _exhausted(self, progress: ConductSliceProgress) -> ConductSliceResult:
        if progress.run.step is Step.AWAIT_MERGE:
            self._repository.flag_draft_pull_request(
                repo=progress.params.repo, issue=progress.subissue.number, pull_request=self._pull_request_of(progress)
            )

        return self._ending(progress, Halt.WAIT_EXHAUSTED)

    def _stepping(self, progress: ConductSliceProgress) -> SteppedSlice | HaltedSlice:
        match progress.run.step:
            case Step.UNDERSTAND | Step.IMPLEMENT | Step.RUN_CONTROLS | Step.VERIFY:
                return self._stepping_while_producing(progress, progress.run.step)
            case Step.OPEN_PULL_REQUEST | Step.AWAIT_CI | Step.AWAIT_MERGE:
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
        self, progress: ConductSliceProgress, step: Literal[Step.OPEN_PULL_REQUEST, Step.AWAIT_CI, Step.AWAIT_MERGE]
    ) -> SteppedSlice | HaltedSlice:
        match step:
            case Step.OPEN_PULL_REQUEST:
                return self._opening_the_pull_request(progress)
            case Step.AWAIT_CI:
                return self._asking_the_ci(progress)
            case Step.AWAIT_MERGE:
                return self._asking_for_the_merge(progress)

    def _implementing(self, progress: ConductSliceProgress) -> SteppedSlice:
        if self._budgets.exhausted(progress.spend):
            return SteppedSlice(progress=progress, outcome=Outcome.OVER_BUDGET)

        progress = self._seeded(progress)

        implementation = self._implement.execute(
            ImplementSliceParams(
                worktree=progress.params.worktree,
                subissue=progress.subissue,
                parent=progress.parent,
                findings=progress.findings_of_the_last_round,
                control_logs=progress.control_logs,
                hygiene_refusal=progress.hygiene_refusal,
                understanding=progress.understanding,
            )
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

        round_progress = replace(progress, control_rounds=progress.control_rounds + 1, hygiene_refusal="")
        outcomes = self._ran_controls(round_progress)
        red = tuple(
            outcome.log for outcome in outcomes if outcome.status is ControlStatus.RED and outcome.log is not None
        )

        return SteppedSlice(
            progress=replace(round_progress, control_logs=red), outcome=Outcome.of_the_controls(outcomes)
        )

    def _ran_controls(self, progress: ConductSliceProgress) -> tuple[ControlOutcome, ...]:
        controls = progress.parent.controls
        if controls.exemption_reason is not None:
            return ()

        out = progress.params.logs / f"round-{progress.control_rounds}"

        return tuple(
            self._controls.run(command, repo=progress.params.worktree, out=out) for command in controls.commands
        )

    def _judging(self, progress: ConductSliceProgress) -> SteppedSlice:
        if self._budgets.exhausted(progress.spend):
            return SteppedSlice(progress=progress, outcome=Outcome.OVER_BUDGET)

        try:
            verification = self._verify.execute(
                VerifySliceParams(
                    repo=progress.params.worktree,
                    base=progress.params.base,
                    slice_id=progress.subissue.slice_id,
                    signal=progress.subissue.signal,
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
            progress, spends=(*progress.spends, verification.spend), verdicts=(*progress.verdicts, verification.verdict)
        )
        stepped = SteppedSlice(progress=judged, outcome=Outcome.of_the_verdict(verification.verdict))
        if verification.verdict.ruling is Ruling.PASS:
            return stepped

        return self._within_budget(stepped, call=verification.spend)

    def _within_budget(self, stepped: SteppedSlice, *, call: HarnessSpend | None) -> SteppedSlice:
        if not self._budgets.cost_exhausted(call=call, total=stepped.progress.spend):
            return stepped

        return replace(stepped, outcome=Outcome.OVER_BUDGET)

    @staticmethod
    def _discarding(progress: ConductSliceProgress, rejection: MeasuredCallError) -> ConductSliceProgress:
        spends = progress.spends if rejection.spend is None else (*progress.spends, rejection.spend)

        return replace(progress, spends=spends, discard_cause=DiscardCause.of_the_rejection(rejection))

    def _opening_the_pull_request(self, progress: ConductSliceProgress) -> SteppedSlice:
        opened = self._deliver.execute(
            DeliverSliceParams(
                worktree=progress.params.worktree,
                repo=progress.params.repo,
                branch=progress.subissue.branch,
                base=progress.params.base,
                title=self._pull_request.title(progress.subissue),
                body=self._pull_request.body(
                    progress.subissue, debt=progress.debt, findings=progress.findings_of_the_last_round
                ),
            )
        )

        return SteppedSlice(progress=replace(progress, pull_request=opened), outcome=Outcome.DONE)

    def _asking_the_ci(self, progress: ConductSliceProgress) -> SteppedSlice:
        opened = self._pull_request_of(progress)
        status = self._ci.status(repo=progress.params.repo, pull_request=opened)

        return SteppedSlice(progress=replace(progress, pull_request=opened), outcome=Outcome.of_the_ci(status))

    def _asking_for_the_merge(self, progress: ConductSliceProgress) -> SteppedSlice | HaltedSlice:
        opened = self._pull_request_of(progress)
        asked = replace(progress, pull_request=opened)

        match self._forum.pull_request_state(repo=progress.params.repo, number=opened):
            case PullRequestState.MERGED:
                return SteppedSlice(progress=asked, outcome=Outcome.DONE)
            case PullRequestState.OPEN:
                return SteppedSlice(progress=asked, outcome=Outcome.PENDING)
            case PullRequestState.CLOSED:
                return HaltedSlice(progress=asked, halt=Halt.PULL_REQUEST_CLOSED)

    def _pull_request_of(self, progress: ConductSliceProgress) -> int:
        if progress.pull_request is not None:
            return progress.pull_request

        opened = self._forum.any_pull_request(repo=progress.params.repo, branch=progress.subissue.branch)
        if opened is None:
            raise NoPullRequestError(
                f"the run of {progress.subissue.slice_id} stands on `{progress.run.step}` and no pull request "
                f"of any state was found for {progress.subissue.branch}"
            )

        return opened

    def _persisted(self, progress: ConductSliceProgress, transition: Transition) -> ConductSliceProgress:
        run = replace(transition.run, spend=progress.spend)
        if run != progress.run:
            self._writing(progress, run=run)
        label = IssueLabel.of(state=transition.state, step=run.step)
        if label is progress.label:
            return replace(progress, run=run)
        if label is None:
            if progress.label is not None:
                self._repository.remove_label(
                    repo=progress.params.repo, issue=progress.subissue.number, remove=progress.label
                )
            return replace(progress, run=run, label=None)

        self._repository.write_label(
            repo=progress.params.repo, issue=progress.subissue.number, remove=progress.label, add=label
        )

        return replace(progress, run=run, label=label)

    def _closing_a_merge_missed_between_invocations(self, params: ConductSliceParams, subissue: SubIssue) -> None:
        run = subissue.run
        if run is None:
            return

        opened = self._forum.any_pull_request(repo=params.repo, branch=subissue.branch)
        if (
            opened is None
            or self._forum.pull_request_state(repo=params.repo, number=opened) is not PullRequestState.MERGED
        ):
            return

        self._metrics.record(
            ClosedSlice(
                repo=params.repo,
                slice_id=subissue.slice_id,
                name=subissue.name,
                state=RunState.MERGED,
                run=run,
                spends=(run.spend,) if run.spend.measured else (),
            )
        )
        label = subissue.label
        if label is not None:
            self._repository.remove_label(repo=params.repo, issue=subissue.number, remove=label)
        self._close.execute(CloseParentParams(repo=params.repo, issue=params.issue))

    def _reporting(self, progress: ConductSliceProgress, transition: Transition) -> None:
        self._events.emit(
            Event(
                slice_id=progress.subissue.slice_id,
                step=transition.run.step,
                at=self._clock.now(),
                spend=progress.spend,
                status=EventStatus.of_the_transition(transition),
            )
        )

    def _writing(self, progress: ConductSliceProgress, *, run: Run) -> None:
        self._repository.write_run(repo=progress.params.repo, issue=progress.subissue.number, run=run)

    def _waiting(self, progress: ConductSliceProgress, seconds: int) -> ConductSliceProgress:
        self._clock.sleep(seconds=seconds)

        return replace(progress, waited_seconds=progress.waited_seconds + seconds)

    def _closing(self, progress: ConductSliceProgress, state: RunState) -> ConductSliceResult:
        self._metrics.record(
            ClosedSlice(
                repo=progress.params.repo,
                slice_id=progress.subissue.slice_id,
                name=progress.subissue.name,
                state=state,
                run=progress.run,
                spends=progress.spends,
                findings=progress.findings_of_every_round,
                findings_of_the_last_round=progress.findings_of_the_last_round,
                discard_cause=progress.discard_cause,
            )
        )
        if state is RunState.MERGED:
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
        precheck: PrecheckOutcome | None = None,
    ) -> ConductSliceResult:
        return ConductSliceResult(
            halt=halt,
            state=state,
            step=progress.run.step,
            precheck=precheck,
            pull_request=progress.pull_request,
        )
