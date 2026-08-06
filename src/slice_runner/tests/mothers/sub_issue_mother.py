from __future__ import annotations

from dataclasses import replace
from typing import ClassVar

from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.sub_issue import SubIssue


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
    def carrying(label: IssueLabel) -> SubIssue:
        return replace(SubIssueMother.pending(), label=label)

    @staticmethod
    def unlabelled() -> SubIssue:
        return replace(SubIssueMother.pending(), label=None)

    @staticmethod
    def without_a_declared_intention() -> SubIssue:
        return replace(SubIssueMother.pending(), intention="")

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
