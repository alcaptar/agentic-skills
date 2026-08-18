from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from slice_runner.application.actions.close_parent import CloseParent
from slice_runner.application.actions.conduct_slice import (
    ConductSlice,
    ConductSliceParams,
    ConductSlicePorts,
    ConductSliceUseCases,
)
from slice_runner.application.actions.deliver_slice import DeliverSlice
from slice_runner.application.actions.implement_slice import ImplementSlice
from slice_runner.application.actions.record_closure import RecordClosure
from slice_runner.application.actions.record_step import RecordStep
from slice_runner.application.actions.reopen_slice import ReopenSlice
from slice_runner.application.actions.reset_slice import ResetSlice, ResetSliceParams
from slice_runner.application.actions.run_controls import RunControls
from slice_runner.application.actions.seek_alignment import SeekAlignment
from slice_runner.application.actions.stage_slice import StageSlice
from slice_runner.application.actions.verify_slice import VerifySlice, VerifySliceParams
from slice_runner.application.queries.check_readiness import CheckReadiness, CheckReadinessParams, CheckReadinessPorts
from slice_runner.application.queries.list_closed_slices import ListClosedSlices, ListClosedSlicesParams
from slice_runner.application.queries.read_ci_status import ReadCiStatus
from slice_runner.application.queries.read_conversation import ReadConversation, ReadConversationParams
from slice_runner.application.queries.read_pull_request_status import ReadPullRequestStatus
from slice_runner.application.queries.run_prechecks import RunPrechecks
from slice_runner.application.queries.select_slice import SelectSlice
from slice_runner.application.queries.show_feature_status import ShowFeatureStatus, ShowFeatureStatusParams
from slice_runner.application.queries.spend_by_role import SpendByRole, SpendByRoleParams
from slice_runner.application.queries.spend_of_step import SpendOfStep, SpendOfStepParams
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.exceptions import (
    BranchMismatchError,
    ConversationNotFoundError,
    DiffNotReadableError,
    ImpossibleTransitionError,
    InvalidHarnessOutputError,
    LaggingSearchIndexError,
    MeasuredCallError,
    MissingBranchError,
    NoConversationRecordedError,
    NoPullRequestError,
    NoRecognizableSpecError,
    NoSliceLeftError,
    ProtectedBranchError,
    RunNotClosedError,
    SourcesBudgetExceededError,
    UnreadableCallSpendLogError,
    UnreadableCallTraceError,
    UnreadableConversationError,
    UnreadableForumError,
    UnreadableIssueError,
    UnreadableMetricsLogError,
    UnreadableRunError,
    UnresolvableRepoOrBaseError,
)
from slice_runner.domain.gh_retry_policy import GhRetryPolicy
from slice_runner.domain.halt import Halt
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.state_machine import StateMachine
from slice_runner.domain.step import Step
from slice_runner.infrastructure.claude_implementer import ClaudeImplementer
from slice_runner.infrastructure.claude_understanding import ClaudeUnderstanding
from slice_runner.infrastructure.claude_verifier import ClaudeVerifier
from slice_runner.infrastructure.closed_slice_metrics_view import ClosedSliceMetricsView
from slice_runner.infrastructure.closed_slice_record_payload import ClosedSliceRecordPayload
from slice_runner.infrastructure.conducted_slice_payload import ConductedSlicePayload
from slice_runner.infrastructure.conversation_report import ConversationReport
from slice_runner.infrastructure.conversation_tool_use_recorder import ConversationToolUseRecorder
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.infrastructure.feature_status_report import FeatureStatusReport
from slice_runner.infrastructure.gh_call import GhCall
from slice_runner.infrastructure.gh_ci import GhCi
from slice_runner.infrastructure.gh_forum import GhForum
from slice_runner.infrastructure.gh_run_repository import GhCommandFailedError, GhRunRepository
from slice_runner.infrastructure.git_branches import GitBranches, GitCommandFailedError
from slice_runner.infrastructure.git_diff_reader import GitDiffReader
from slice_runner.infrastructure.git_workspace import GitWorkspace
from slice_runner.infrastructure.harness_telemetry import HarnessTelemetry
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.local_call_spend_log import LocalCallSpendLog
from slice_runner.infrastructure.local_call_trace import LocalCallTrace
from slice_runner.infrastructure.local_control_runner import LocalControlRunner
from slice_runner.infrastructure.local_conversation_log import LocalConversationLog
from slice_runner.infrastructure.local_corpus import LocalCorpus
from slice_runner.infrastructure.local_metrics_log import LocalMetricsLog
from slice_runner.infrastructure.local_plugin_registry import LocalPluginRegistry
from slice_runner.infrastructure.local_process import LocalProcess
from slice_runner.infrastructure.local_skill_library import LocalSkillLibrary
from slice_runner.infrastructure.local_tool_use_log import LocalToolUseLog
from slice_runner.infrastructure.local_toolbox import LocalToolbox
from slice_runner.infrastructure.muted_deploy_watch import MutedDeployWatch
from slice_runner.infrastructure.process import ProcessNotRunnableError, ProcessTimedOutError
from slice_runner.infrastructure.process_source_reader import ProcessSourceReader
from slice_runner.infrastructure.readiness_report import ReadinessReport
from slice_runner.infrastructure.slice_pull_request import SlicePullRequest
from slice_runner.infrastructure.slice_verifier_judge import SliceVerifierJudge
from slice_runner.infrastructure.spend_payload import SpendPayload
from slice_runner.infrastructure.stderr_event_log import StderrEventLog
from slice_runner.infrastructure.stderr_turn_log import StderrTurnLog
from slice_runner.infrastructure.subcommand import Subcommand
from slice_runner.infrastructure.system_clock import SystemClock
from slice_runner.infrastructure.transition_payload import TransitionPayload
from slice_runner.infrastructure.transition_request_payload import TransitionRequestPayload
from slice_runner.infrastructure.understanding_invocation import UnderstandingInvocation
from slice_runner.infrastructure.uv_program_origin import UvProgramOrigin
from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.application.actions.conduct_slice import ConductSliceResult
    from slice_runner.domain.clock import Clock
    from slice_runner.infrastructure.process import Process


class Cli:
    PROGRAM: ClassVar[str] = "slice-runner"
    LOGS: ClassVar[Path] = Path(tempfile.gettempdir()) / "slice-runner-logs"
    STOPS: ClassVar[tuple[type[Exception], ...]] = (
        NoSliceLeftError,
        UnresolvableRepoOrBaseError,
        UnreadableIssueError,
        UnreadableRunError,
        ImpossibleTransitionError,
        ProtectedBranchError,
        BranchMismatchError,
        MissingBranchError,
        DiffNotReadableError,
        MeasuredCallError,
        ProcessTimedOutError,
        UnreadableForumError,
        LaggingSearchIndexError,
        NoPullRequestError,
        RunNotClosedError,
        GhCommandFailedError,
        GitCommandFailedError,
        ProcessNotRunnableError,
        SourcesBudgetExceededError,
    )

    def __init__(self, *, process: Process, budgets: Budgets) -> None:
        self._process = process
        self._budgets = budgets

    @classmethod
    def main(cls, argv: list[str] | None = None) -> int:
        try:
            arguments = cls.parser().parse_args(argv)
        except SystemExit as refusal:
            return ExitCode.USAGE_ERROR if refusal.code else ExitCode.OK

        try:
            return cls._dispatched(arguments)
        except Exception as error:
            return cls._reported(f"{type(error).__name__}: {error}", ExitCode.RUN_INTERRUPTED)

    @classmethod
    def _dispatched(cls, arguments: argparse.Namespace) -> int:
        budgets = Budgets()

        match Subcommand(arguments.command):
            case Subcommand.VERIFY:
                result = cls(process=LocalProcess(budgets=budgets), budgets=budgets).verify(
                    repo=arguments.repo, base=arguments.base, slice_id=arguments.slice_id
                )
            case Subcommand.EXPLAIN:
                result = cls.explain(request=sys.stdin.read(), budgets=budgets)
            case Subcommand.RUN:
                result = cls(process=LocalProcess(budgets=budgets), budgets=budgets).run(
                    ConductSliceParams(
                        repo=arguments.repo,
                        issue=arguments.issue,
                        worktree=arguments.worktree,
                        base=arguments.base,
                        logs=arguments.logs,
                        slice_id=arguments.slice_id,
                    )
                )
            case Subcommand.READ:
                result = cls.read(
                    repo=arguments.repo,
                    issue=arguments.issue,
                    worktree=arguments.worktree,
                    slice_id=arguments.slice_id,
                    step=Step(arguments.step),
                )
            case Subcommand.SPEND:
                result = cls.spend(
                    repo=arguments.repo, issue=arguments.issue, slice_id=arguments.slice_id, step=Step(arguments.step)
                )
            case Subcommand.DOCTOR:
                result = cls(process=LocalProcess(budgets=budgets), budgets=budgets).doctor(
                    repo=arguments.repo, worktree=arguments.worktree, base=arguments.base
                )
            case Subcommand.METRICS:
                result = cls.metrics(
                    repo=arguments.repo,
                    since=cls._parsed_date(arguments.since, default=datetime(1970, 1, 1, tzinfo=UTC)),
                    until=cls._parsed_date(arguments.until, default=SystemClock().now()),
                    out=arguments.out,
                )
            case Subcommand.RESET:
                result = cls(process=LocalProcess(budgets=budgets), budgets=budgets).reset(
                    repo=arguments.repo, issue=arguments.issue
                )
            case Subcommand.STATUS:
                result = cls(process=LocalProcess(budgets=budgets), budgets=budgets).status(
                    repo=arguments.repo, issue=arguments.issue
                )

        return result

    @classmethod
    def parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog=cls.PROGRAM,
            description="Slice orchestrator. See the README for the design.",
        )
        subcommands = parser.add_subparsers(dest="command", required=True)

        verify = subcommands.add_parser(Subcommand.VERIFY, help="judge the index of a slice against its base")
        verify.add_argument("--repo", required=True, help="path of the slice's repo")
        verify.add_argument("--base", required=True, help="base branch the diff is taken against")
        verify.add_argument(
            "--slice", dest="slice_id", required=True, help="identifier of the slice the verdict belongs to"
        )

        subcommands.add_parser(
            Subcommand.EXPLAIN, help="say what comes after the run and the outcome read on standard input"
        )

        run = subcommands.add_parser(Subcommand.RUN, help="conduct the next slice of an issue until it has to stop")
        run.add_argument("issue", type=int, help="number of the issue whose next slice is conducted")
        run.add_argument("--repo", required=True, help="repo of the issue, as `<org>/<repo>`")
        run.add_argument("--worktree", default=".", help="local path where the slice is implemented and measured")
        run.add_argument("--base", required=True, help="branch the diff is taken against and the pull request targets")
        run.add_argument(
            "--logs", type=Path, default=cls.LOGS, help="directory where the log of each control is written"
        )
        run.add_argument(
            "--slice",
            dest="slice_id",
            default=None,
            help=(
                "identifier of the one slice to conduct, e.g. `slice-01`, or `PROJ-1234-01` when the feature "
                "declares a user story; without it, the next runnable one is chosen"
            ),
        )

        read = subcommands.add_parser(
            Subcommand.READ, help="print the conversation of the last call that served a slice's step, as text"
        )
        read.add_argument("--repo", required=True, help="repo of the issue the slice belongs to, as `<org>/<repo>`")
        read.add_argument("--issue", type=int, required=True, help="number of the subissue the slice belongs to")
        read.add_argument("--worktree", required=True, help="path of the slice's repo, as it was when the call ran")
        read.add_argument("--slice", dest="slice_id", required=True, help="identifier of the slice to read")
        read.add_argument("--step", required=True, choices=[str(x) for x in Step], help="step whose call is read")

        spend = subcommands.add_parser(
            Subcommand.SPEND, help="add up what the harness spent on the calls that served a slice's step"
        )
        spend.add_argument("--repo", required=True, help="repo of the issue the slice belongs to, as `<org>/<repo>`")
        spend.add_argument("--issue", type=int, required=True, help="number of the subissue the slice belongs to")
        spend.add_argument("--slice", dest="slice_id", required=True, help="identifier of the slice to add up")
        spend.add_argument("--step", required=True, choices=[str(x) for x in Step], help="step whose calls are summed")

        doctor = subcommands.add_parser(
            Subcommand.DOCTOR, help="check whether git, gh, claude and the skills the run needs are in place"
        )
        doctor.add_argument("--repo", default=None, help="repo to check read access to, as `<org>/<repo>`")
        doctor.add_argument(
            "--worktree", default=None, help="local path whose base branch is compared against its remote"
        )
        doctor.add_argument("--base", default=None, help="base branch compared against its remote")

        metrics = subcommands.add_parser(
            Subcommand.METRICS, help="emit the closed slices of a window already joined, and their view"
        )
        metrics.add_argument("--repo", default=None, help="limit to one repo, as `<org>/<repo>` (default: every repo)")
        metrics.add_argument("--since", default=None, help="earliest date included, as `YYYY-MM-DD` (default: all)")
        metrics.add_argument("--until", default=None, help="latest date included, as `YYYY-MM-DD` (default: now)")
        metrics.add_argument("--out", type=Path, required=True, help="path where the HTML view is written")

        reset = subcommands.add_parser(
            Subcommand.RESET,
            help="clear a subissue's persisted run and label it pending again, without touching git",
        )
        reset.add_argument("issue", type=int, help="number of the subissue to reset")
        reset.add_argument("--repo", required=True, help="repo of the issue the subissue belongs to")

        status = subcommands.add_parser(
            Subcommand.STATUS,
            help="print one line per slice of an issue with its state, step, spend and pull request, reading only",
        )
        status.add_argument("issue", type=int, help="number of the parent issue whose slices are shown")
        status.add_argument("--repo", required=True, help="repo of the issue, as `<org>/<repo>`")

        return parser

    @classmethod
    def explain(cls, *, request: str, budgets: Budgets) -> int:
        try:
            asked = TransitionRequestPayload.read(request)
            transition = StateMachine(budgets=budgets).after(asked.run.to_domain(), asked.outcome)
        except (ImpossibleTransitionError, UnreadableRunError) as error:
            return cls._reported(f"there is no transition to explain: {error}", ExitCode.USAGE_ERROR)

        print(json.dumps(TransitionPayload.from_domain(transition).to_contract(), ensure_ascii=False))

        return ExitCode.OK

    @classmethod
    def read(cls, *, repo: str, issue: int, worktree: str, slice_id: str, step: Step) -> int:
        clock = SystemClock()
        try:
            result = ReadConversation(trace=LocalCallTrace(clock=clock), log=LocalConversationLog()).execute(
                ReadConversationParams(repo=repo, issue=issue, worktree=worktree, slice_id=slice_id, step=step)
            )
        except (NoConversationRecordedError, ConversationNotFoundError) as error:
            return cls._reported(f"there is no conversation to read: {error}", ExitCode.USAGE_ERROR)
        except (UnreadableCallTraceError, UnreadableConversationError) as error:
            return cls._reported(f"the durable record cannot be read: {error}", ExitCode.USAGE_ERROR)

        print(
            ConversationReport(
                slice_id=slice_id, step=step, session=result.session, conversation=result.conversation
            ).rendered()
        )

        return ExitCode.OK

    @classmethod
    def spend(cls, *, repo: str, issue: int, slice_id: str, step: Step) -> int:
        clock = SystemClock()
        try:
            spend = SpendOfStep(trace=LocalCallTrace(clock=clock), spend_log=LocalCallSpendLog(clock=clock)).execute(
                SpendOfStepParams(repo=repo, issue=issue, slice_id=slice_id, step=step)
            )
        except (UnreadableCallTraceError, UnreadableCallSpendLogError) as error:
            return cls._reported(f"the durable record cannot be read: {error}", ExitCode.USAGE_ERROR)

        print(json.dumps(SpendPayload.from_domain(spend).to_contract(), ensure_ascii=False))

        return ExitCode.OK

    @classmethod
    def metrics(cls, *, repo: str | None, since: datetime, until: datetime, out: Path) -> int:
        clock = SystemClock()
        try:
            records = ListClosedSlices(metrics_log=LocalMetricsLog(clock=clock)).execute(
                ListClosedSlicesParams(repo=repo, since=since, until=until)
            )
            role_spend = SpendByRole(
                trace=LocalCallTrace(clock=clock), spend_log=LocalCallSpendLog(clock=clock)
            ).execute(SpendByRoleParams(records=records))
        except (UnreadableCallTraceError, UnreadableCallSpendLogError, UnreadableMetricsLogError) as error:
            return cls._reported(f"the durable record cannot be read: {error}", ExitCode.USAGE_ERROR)

        for record in records:
            print(json.dumps(ClosedSliceRecordPayload.from_domain(record).to_contract(), ensure_ascii=False))

        view = ClosedSliceMetricsView.rendered(
            repo=repo, since=since, until=until, records=records, role_spend=role_spend
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(view, encoding="utf-8")

        return ExitCode.OK

    @staticmethod
    def _parsed_date(value: str | None, *, default: datetime) -> datetime:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC) if value else default

    def verify(self, *, repo: str, base: str, slice_id: str) -> int:
        try:
            verification = self._action().execute(self._params(worktree=repo, base=base, slice_id=slice_id))
        except (
            UnresolvableRepoOrBaseError,
            DiffNotReadableError,
            InvalidHarnessOutputError,
            ProcessTimedOutError,
            ProcessNotRunnableError,
            SourcesBudgetExceededError,
        ) as error:
            return self._why_verify_failed(error)

        self._warn_about(verification.denied_reads)
        print(json.dumps(VerdictPayload.from_domain(verification.verdict).to_contract(), ensure_ascii=False))

        return ExitCode.of(verification.verdict.ruling)

    def _why_verify_failed(
        self,
        error: UnresolvableRepoOrBaseError
        | DiffNotReadableError
        | InvalidHarnessOutputError
        | ProcessTimedOutError
        | ProcessNotRunnableError
        | SourcesBudgetExceededError,
    ) -> int:
        match error:
            case UnresolvableRepoOrBaseError():
                return self._reported(f"the repo or the base requested do not resolve: {error}", ExitCode.USAGE_ERROR)
            case DiffNotReadableError():
                return self._reported(f"there is no diff to verify: {error}", ExitCode.NO_DIFF)
            case InvalidHarnessOutputError():
                return self._reported(f"the judge left no usable verdict: {error}", ExitCode.NO_USABLE_VERDICT)
            case ProcessTimedOutError():
                return self._reported(
                    f"a process the run needs never came back and was killed at its cap: {error}",
                    ExitCode.PROCESS_TIMED_OUT,
                )
            case ProcessNotRunnableError():
                return self._reported(
                    f"a process the run needs could not be launched, so there is no verdict: {error}",
                    ExitCode.NO_USABLE_VERDICT,
                )
            case SourcesBudgetExceededError():
                return self._reported(
                    f"the declared sources are over the budget, so no prompt was sent: {error}",
                    ExitCode.SOURCES_BUDGET_EXCEEDED,
                )

    def run(self, params: ConductSliceParams) -> int:
        params.logs.mkdir(parents=True, exist_ok=True)

        try:
            conducted = self._conductor().execute(params)
        except self.STOPS as error:
            return self._why_the_run_stopped(error)

        self._warn_about_the_draft_pull_request(conducted)
        print(json.dumps(ConductedSlicePayload.from_domain(conducted).to_contract(), ensure_ascii=False))

        return ExitCode.of_the_halt(halt=conducted.halt, state=conducted.state)

    @staticmethod
    def _warn_about_the_draft_pull_request(conducted: ConductSliceResult) -> None:
        if conducted.halt is not Halt.WAIT_EXHAUSTED or conducted.step is not Step.AWAIT_MERGE:
            return

        print(
            f"pull request #{conducted.pull_request} was opened as a draft; take it out of draft for the merge "
            "to happen, reinvoking alone will not move it",
            file=sys.stderr,
        )

    def doctor(self, *, repo: str | None = None, worktree: str | None = None, base: str | None = None) -> int:
        readiness = CheckReadiness(
            ports=CheckReadinessPorts(
                toolbox=LocalToolbox(process=self._process),
                forum=GhForum(call=self._gh_call(clock=SystemClock())),
                branches=GitBranches(process=self._process),
                skills=LocalSkillLibrary(),
                plugins=LocalPluginRegistry(),
                provenance=UvProgramOrigin(),
            )
        ).execute(CheckReadinessParams(repo=repo, worktree=worktree, base=base))

        print(ReadinessReport(readiness=readiness).rendered())

        return ExitCode.OK if readiness.ready else ExitCode.ENVIRONMENT_NOT_READY

    def reset(self, *, repo: str, issue: int) -> int:
        clock = SystemClock()
        repository = GhRunRepository(call=self._gh_call(clock=clock))
        try:
            subissue = repository.read_subissue(repo=repo, issue=issue)
            reset = ResetSlice(repository=repository, clock=clock).execute(
                ResetSliceParams(repo=repo, subissue=subissue)
            )
        except (UnreadableIssueError, UnreadableRunError, NoRecognizableSpecError) as error:
            return self._reported(f"there is no spec to reset: {error}", ExitCode.USAGE_ERROR)
        except GhCommandFailedError as error:
            return self._reported(f"the reset could not be written: {error}", ExitCode.RUN_INTERRUPTED)

        print(
            f"subissue #{issue} was reset to `{reset.subissue.label}`; the branch `{reset.subissue.branch}` and "
            "the working tree were left untouched"
        )

        return ExitCode.OK

    def status(self, *, repo: str, issue: int) -> int:
        clock = SystemClock()
        gh_call = self._gh_call(clock=clock)
        try:
            statuses = ShowFeatureStatus(
                repository=GhRunRepository(call=gh_call),
                forum=GhForum(call=gh_call),
                metrics=LocalMetricsLog(clock=clock),
            ).execute(ShowFeatureStatusParams(repo=repo, issue=issue))
        except (
            LaggingSearchIndexError,
            UnreadableIssueError,
            UnreadableForumError,
            UnreadableMetricsLogError,
        ) as error:
            return self._reported(f"the status of the feature could not be read: {error}", ExitCode.USAGE_ERROR)
        except GhCommandFailedError as error:
            return self._reported(f"the status of the feature could not be read: {error}", ExitCode.RUN_INTERRUPTED)

        print(FeatureStatusReport(statuses=statuses).rendered())

        return ExitCode.OK

    def _why_the_run_stopped(self, error: Exception) -> ExitCode:
        match error:
            case NoSliceLeftError():
                return self._reported(f"there is no slice left to run: {error}", ExitCode.NO_SLICE_LEFT)
            case (
                UnresolvableRepoOrBaseError()
                | UnreadableIssueError()
                | UnreadableRunError()
                | ImpossibleTransitionError()
                | ProtectedBranchError()
                | BranchMismatchError()
                | MissingBranchError()
            ):
                return self._reported(f"the run cannot be conducted as asked: {error}", ExitCode.USAGE_ERROR)
            case DiffNotReadableError():
                return self._reported(f"there is no diff to verify: {error}", ExitCode.NO_DIFF)
            case MeasuredCallError():
                return self._reported(f"the harness left nothing usable behind: {error}", ExitCode.NO_USABLE_VERDICT)
            case ProcessTimedOutError() | SourcesBudgetExceededError():
                return self._why_the_call_failed(error)
            case _:
                return self._reported(f"the run stopped before reaching a halt: {error}", ExitCode.RUN_INTERRUPTED)

    def _why_the_call_failed(self, error: ProcessTimedOutError | SourcesBudgetExceededError) -> ExitCode:
        match error:
            case ProcessTimedOutError():
                return self._reported(
                    f"a call the run made never came back and was killed at its cap: {error}",
                    ExitCode.PROCESS_TIMED_OUT,
                )
            case SourcesBudgetExceededError():
                return self._reported(
                    f"the declared sources are over the budget, so no prompt was sent: {error}",
                    ExitCode.SOURCES_BUDGET_EXCEEDED,
                )

    def _conductor(self) -> ConductSlice:
        clock = SystemClock()
        gh_call = self._gh_call(clock=clock)
        repository = GhRunRepository(call=gh_call)
        branches = GitBranches(process=self._process)
        forum = GhForum(call=gh_call)
        workspace = GitWorkspace(process=self._process)
        machine = StateMachine(budgets=self._budgets)
        reader = ProcessSourceReader(process=self._process, budgets=self._budgets)

        return ConductSlice(
            use_cases=ConductSliceUseCases(
                select=SelectSlice(repository=repository),
                reopen=ReopenSlice(repository=repository, machine=machine),
                prechecks=RunPrechecks(branches=branches, forum=forum, sources=reader),
                implement=ImplementSlice(
                    implementer=ClaudeImplementer(
                        process=self._process,
                        telemetry=HarnessTelemetry(
                            trace=LocalCallTrace(clock=clock),
                            turns=StderrTurnLog(),
                            spend_log=LocalCallSpendLog(clock=clock),
                            tool_uses=self._tool_uses(),
                        ),
                        reader=reader,
                    )
                ),
                stage=StageSlice(workspace=workspace),
                run_controls=RunControls(controls=LocalControlRunner(process=self._process)),
                verify=self._action(clock=clock),
                deliver=DeliverSlice(workspace=workspace, forum=forum),
                close=CloseParent(repository=repository),
                record_step=RecordStep(repository=repository, events=StderrEventLog(), clock=clock),
                record_closure=RecordClosure(metrics=LocalMetricsLog(clock=clock), repository=repository),
                read_ci=ReadCiStatus(ci=GhCi(call=gh_call), forum=forum),
                read_pull_request=ReadPullRequestStatus(forum=forum),
                seek_alignment=SeekAlignment(
                    understanding=ClaudeUnderstanding(
                        process=self._process,
                        telemetry=HarnessTelemetry(
                            trace=LocalCallTrace(clock=clock),
                            turns=StderrTurnLog(),
                            spend_log=LocalCallSpendLog(clock=clock),
                            tool_uses=self._tool_uses(),
                        ),
                        reader=reader,
                    ),
                    repository=repository,
                ),
            ),
            ports=ConductSlicePorts(
                repository=repository,
                branches=branches,
                forum=forum,
                clock=clock,
                pull_request=SlicePullRequest(),
                deploy_watch=MutedDeployWatch(),
            ),
            machine=machine,
            budgets=self._budgets,
            models=RoleModels(
                understand=UnderstandingInvocation.MODEL,
                implement=ImplementerInvocation.MODEL,
                verify=JudgeInvocation.MODEL,
            ),
        )

    def _gh_call(self, *, clock: Clock) -> GhCall:
        return GhCall(process=self._process, policy=GhRetryPolicy(budgets=self._budgets), clock=clock)

    def _action(self, *, clock: Clock | None = None) -> VerifySlice:
        used = clock or SystemClock()

        return VerifySlice(
            reader=GitDiffReader(process=self._process),
            verifier=ClaudeVerifier(
                process=self._process,
                telemetry=HarnessTelemetry(
                    trace=LocalCallTrace(clock=used),
                    turns=StderrTurnLog(),
                    spend_log=LocalCallSpendLog(clock=used),
                    tool_uses=self._tool_uses(),
                ),
                reader=ProcessSourceReader(process=self._process, budgets=self._budgets),
            ),
            judge=SliceVerifierJudge.adversarial(),
            skills=LocalSkillLibrary(),
            corpus=LocalCorpus(clock=used),
        )

    @staticmethod
    def _tool_uses() -> ConversationToolUseRecorder:
        return ConversationToolUseRecorder(conversations=LocalConversationLog(), tool_use_log=LocalToolUseLog())

    @staticmethod
    def _warn_about(denied_reads: tuple[str, ...]) -> None:
        if not denied_reads:
            return

        print(
            f"the judge was denied {len(denied_reads)} read(s), so it may have measured with an incomplete "
            f"yardstick: {', '.join(denied_reads)}",
            file=sys.stderr,
        )

    @staticmethod
    def _params(*, worktree: str, base: str, slice_id: str) -> VerifySliceParams:
        return VerifySliceParams(
            repo="",
            issue=0,
            worktree=worktree,
            base=base,
            slice_id=slice_id,
            prior_art="",
            signal="",
            criteria=(),
            sources=(),
            checklist=(),
        )

    @staticmethod
    def _reported(reason: str, code: ExitCode) -> ExitCode:
        print(reason, file=sys.stderr)

        return code
