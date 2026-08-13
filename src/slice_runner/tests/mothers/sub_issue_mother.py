from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.run import Run
from slice_runner.domain.step import Step
from slice_runner.domain.sub_issue import SubIssue
from slice_runner.tests.mothers.run_mother import RunMother

if TYPE_CHECKING:
    from slice_runner.domain.harness_spend import HarnessSpend


class SubIssueMother:
    OTHER_REPO: ClassVar[str] = "alcaptar/otro-repo"

    @staticmethod
    def pending() -> SubIssue:
        return SubIssue(
            number=45,
            slice_id="slice-05",
            name="prechecks-deterministas",
            summary="comprobar antes de tocar codigo",
            title="slice-05 (prechecks-deterministas): comprobar antes de tocar codigo",
            state=IssueState.OPEN,
            repo=None,
            intention="hoy nada evita reimplementar una slice ya entregada",
            criteria=(
                "antes de tocar codigo comprueba que la subissue no este ya cerrada",
                "cada precheck falla con un motivo distinguible, no con un booleano",
            ),
            signal="exenta - este repo no despliega",
            run=None,
            label=IssueLabel.PENDING,
        )

    @staticmethod
    def closed() -> SubIssue:
        return replace(SubIssueMother.pending(), state=IssueState.CLOSED)

    @staticmethod
    def dangling() -> SubIssue:
        return replace(
            SubIssueMother.pending(),
            state=IssueState.CLOSED,
            run=RunMother.awaiting_merge(),
            label=IssueLabel.AWAITING_MERGE,
        )

    @staticmethod
    def carrying(label: IssueLabel) -> SubIssue:
        return replace(SubIssueMother.pending(), label=label)

    @staticmethod
    def blocked(label: IssueLabel, run: Run) -> SubIssue:
        return replace(SubIssueMother.pending(), label=label, run=run)

    @staticmethod
    def paused_after_spending(spend: HarnessSpend) -> SubIssue:
        return replace(
            SubIssueMother.pending(),
            label=IssueLabel.AWAITING_ALIGNMENT,
            run=Run(step=Step.UNDERSTAND, spend=spend),
        )

    @staticmethod
    def unlabelled() -> SubIssue:
        return replace(SubIssueMother.pending(), label=None)

    @staticmethod
    def understanding_published_but_relabelled_by_hand() -> SubIssue:
        return replace(SubIssueMother.pending(), run=Run(step=Step.UNDERSTAND))

    @staticmethod
    def without_a_declared_intention() -> SubIssue:
        return replace(SubIssueMother.pending(), intention="")

    @staticmethod
    def without_a_recognizable_spec() -> SubIssue:
        return replace(SubIssueMother.pending(), intention="", criteria=())

    @staticmethod
    def with_a_single_criterion() -> SubIssue:
        return replace(
            SubIssueMother.pending(),
            criteria=("cada precheck falla con un motivo distinguible, no con un booleano",),
        )

    @staticmethod
    def of_another_repo() -> SubIssue:
        return replace(
            SubIssueMother.pending(),
            number=46,
            slice_id="slice-06",
            name="pausa-de-alineacion",
            summary="el entendimiento se escribe siempre",
            title="slice-06 (pausa-de-alineacion): el entendimiento se escribe siempre",
            repo=SubIssueMother.OTHER_REPO,
        )

    @staticmethod
    def declaring_a_signal() -> SubIssue:
        return replace(SubIssueMother.pending(), signal="tasa de error 5xx de shop-web en produccion")
