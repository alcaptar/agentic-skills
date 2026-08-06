from __future__ import annotations

from slice_runner.infrastructure.slice_pull_request import SlicePullRequest
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother


class TestSlicePullRequest:
    def test_the_title_is_a_conventional_commit_scoped_by_the_name_of_the_slice(self) -> None:
        title = SlicePullRequest().title(SubIssueMother.pending())

        assert title == "feat(prechecks-deterministas): comprobar antes de tocar codigo"

    def test_the_body_carries_the_intention_the_criteria_and_the_signal_the_subissue_declared(self) -> None:
        body = SlicePullRequest().body(SubIssueMother.pending())

        assert body == (
            "## Intencion\n"
            "hoy nada evita reimplementar una slice ya entregada\n"
            "\n"
            "## Criterios de aceptacion cumplidos\n"
            "- antes de tocar codigo comprueba que la subissue no este ya cerrada\n"
            "- cada precheck falla con un motivo distinguible, no con un booleano\n"
            "\n"
            "## Senal a comprobar tras el despliegue\n"
            "exenta - este repo no despliega\n"
            "\n"
            "Closes #45"
        )

    def test_a_slice_that_declared_no_intention_says_so_in_the_heading_instead_of_presenting_it_as_declared(
        self,
    ) -> None:
        body = SlicePullRequest().body(SubIssueMother.without_a_declared_intention())

        assert body.startswith("## Intencion (inferida del issue, no declarada)\n")
