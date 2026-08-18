from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import Mock, create_autospec

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
from slice_runner.application.actions.run_controls import RunControls
from slice_runner.application.actions.seek_alignment import SeekAlignment
from slice_runner.application.actions.stage_slice import StageSlice
from slice_runner.application.actions.verify_slice import VerifySlice
from slice_runner.application.queries.read_ci_status import ReadCiStatus
from slice_runner.application.queries.read_pull_request_status import ReadPullRequestStatus
from slice_runner.application.queries.run_prechecks import RunPrechecks
from slice_runner.application.queries.select_slice import SelectSlice
from slice_runner.domain.alignment_response import AlignmentResponse
from slice_runner.domain.alignment_response_kind import AlignmentResponseKind
from slice_runner.domain.branches import Branches
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.ci import Ci
from slice_runner.domain.ci_status import CiStatus
from slice_runner.domain.clock import Clock
from slice_runner.domain.control_runner import ControlRunner
from slice_runner.domain.deploy_watch import DeployWatch
from slice_runner.domain.event_log import EventLog
from slice_runner.domain.forum import Forum
from slice_runner.domain.metrics_log import MetricsLog
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.precheck_result import PrecheckResult
from slice_runner.domain.pull_request_writer import PullRequestWriter
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.run_repository import RunRepository
from slice_runner.domain.state_machine import StateMachine
from slice_runner.domain.understanding_writer import UnderstandingWriter
from slice_runner.tests.mothers.control_outcome_mother import ControlOutcomeMother
from slice_runner.tests.mothers.implementation_mother import ImplementationMother
from slice_runner.tests.mothers.pull_request_status_mother import PullRequestStatusMother
from slice_runner.tests.mothers.understanding_mother import UnderstandingMother
from slice_runner.tests.mothers.verification_mother import VerificationMother

if TYPE_CHECKING:
    from slice_runner.application.actions.conduct_slice import ConductSliceResult
    from slice_runner.application.queries.select_slice import SelectSliceResult
    from slice_runner.domain.closed_slice import ClosedSlice
    from slice_runner.domain.event import Event


class Conductor:
    REPO: ClassVar[str] = "alcaptar/agentic-skills"
    ISSUE: ClassVar[int] = 38
    WORKTREE: ClassVar[str] = "/repos/agentic-skills"
    BASE: ClassVar[str] = "master"
    LOGS: ClassVar[Path] = Path("/tmp/slice-runner/logs")
    PULL_REQUEST: ClassVar[int] = 61
    TITLE: ClassVar[str] = "feat(prechecks-deterministas): comprobar antes de tocar codigo"
    BODY: ClassVar[str] = "## Intencion\nhoy nada evita reimplementar una slice ya entregada\n\nCloses #45"
    UNDERSTANDING: ClassVar[str] = UnderstandingMother.TEXT
    NOW: ClassVar[datetime] = datetime(2024, 1, 1, tzinfo=UTC)

    MODELS: ClassVar[RoleModels] = RoleModels(understand="sonnet", implement="sonnet", verify="sonnet")

    def __init__(
        self, *, chosen: SelectSliceResult, budgets: Budgets | None = None, models: RoleModels | None = None
    ) -> None:
        self.budgets = budgets or Budgets()
        self.models = models or self.MODELS
        self.select = self._doubling(SelectSlice, execute=chosen)
        self.reopen = self._doubling(ReopenSlice, execute=None)
        self.prechecks = self._doubling(RunPrechecks, execute=PrecheckResult(outcome=PrecheckOutcome.CLEAR))
        self.implement = self._doubling(ImplementSlice, execute=ImplementationMother.of_two_paths())
        self.stage = self._doubling(StageSlice, execute=None)
        self.verify = self._doubling(VerifySlice, execute=VerificationMother.passing())
        self.deliver = self._doubling(DeliverSlice, execute=self.PULL_REQUEST)
        self.close = self._doubling(CloseParent, execute=None)
        self.repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        self.repository.read_alignment_response.return_value = AlignmentResponse(kind=AlignmentResponseKind.NOT_YET)
        self.repository.read_understanding.return_value = self.UNDERSTANDING
        self.branches: Mock = create_autospec(Branches, spec_set=True, instance=True)
        self.controls: Mock = create_autospec(ControlRunner, spec_set=True, instance=True)
        self.controls.run.return_value = ControlOutcomeMother.green()
        self.ci: Mock = create_autospec(Ci, spec_set=True, instance=True)
        self.ci.status.return_value = CiStatus.GREEN
        self.forum: Mock = create_autospec(Forum, spec_set=True, instance=True)
        self.forum.pull_request_state.return_value = PullRequestStatusMother.merged()
        self.forum.open_pull_request.return_value = self.PULL_REQUEST
        self.forum.any_pull_request.return_value = self.PULL_REQUEST
        self.forum.reviews.return_value = ()
        self.clock: Mock = create_autospec(Clock, spec_set=True, instance=True)
        self.clock.now.return_value = self.NOW
        self.metrics: Mock = create_autospec(MetricsLog, spec_set=True, instance=True)
        self.understanding: Mock = create_autospec(UnderstandingWriter, spec_set=True, instance=True)
        self.understanding.write.return_value = UnderstandingMother.of_the_chosen_slice()
        self.pull_request: Mock = create_autospec(PullRequestWriter, spec_set=True, instance=True)
        self.pull_request.title.return_value = self.TITLE
        self.pull_request.body.return_value = self.BODY
        self.deploy_watch: Mock = create_autospec(DeployWatch, spec_set=True, instance=True)
        self.events: Mock = create_autospec(EventLog, spec_set=True, instance=True)

    @property
    def emitted_events(self) -> list[Event]:
        return [call.args[0] for call in self.events.emit.call_args_list]

    @property
    def closed(self) -> ClosedSlice:
        closed: ClosedSlice = self.metrics.record.call_args.args[0]

        return closed

    def conduct(self) -> ConductSliceResult:
        return self._action().execute(
            ConductSliceParams(repo=self.REPO, issue=self.ISSUE, worktree=self.WORKTREE, base=self.BASE, logs=self.LOGS)
        )

    def _action(self) -> ConductSlice:
        return ConductSlice(
            use_cases=ConductSliceUseCases(
                select=self.select,
                reopen=self.reopen,
                prechecks=self.prechecks,
                implement=self.implement,
                stage=self.stage,
                run_controls=RunControls(controls=self.controls),
                verify=self.verify,
                deliver=self.deliver,
                close=self.close,
                record_step=RecordStep(repository=self.repository, events=self.events, clock=self.clock),
                record_closure=RecordClosure(metrics=self.metrics, repository=self.repository),
                read_ci=ReadCiStatus(ci=self.ci, forum=self.forum),
                read_pull_request=ReadPullRequestStatus(forum=self.forum),
                seek_alignment=SeekAlignment(understanding=self.understanding, repository=self.repository),
            ),
            ports=ConductSlicePorts(
                repository=self.repository,
                branches=self.branches,
                forum=self.forum,
                clock=self.clock,
                pull_request=self.pull_request,
                deploy_watch=self.deploy_watch,
            ),
            machine=StateMachine(budgets=self.budgets),
            budgets=self.budgets,
            models=self.models,
        )

    @staticmethod
    def _doubling(use_case: type, *, execute: object) -> Mock:
        double: Mock = create_autospec(use_case, spec_set=True, instance=True)
        double.execute.return_value = execute

        return double
