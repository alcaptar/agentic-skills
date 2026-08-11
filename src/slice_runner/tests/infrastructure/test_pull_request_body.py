from __future__ import annotations

from slice_runner.infrastructure.pull_request_body import PullRequestBody
from slice_runner.tests.mothers.verdict_mother import FindingMother

_INTENTION = "sin esto el programa verifica y no entrega, asi que ningun run puede terminar"
_CRITERIA = (
    "stagea exactamente las rutas declaradas por el implementador",
    "nunca commitea en master ni en main",
)
_SIGNAL = "exenta - este repo no despliega"


class TestPullRequestBody:
    @staticmethod
    def _with_debt() -> PullRequestBody:
        return PullRequestBody(
            intention=_INTENTION,
            criteria=_CRITERIA,
            debt=("el cableado del subcomando queda para la slice-09",),
            findings=(),
            signal=_SIGNAL,
            subissue=46,
        )

    @staticmethod
    def _without_debt() -> PullRequestBody:
        return PullRequestBody(
            intention=_INTENTION, criteria=_CRITERIA, debt=(), findings=(), signal=_SIGNAL, subissue=46
        )

    def test_the_body_a_person_reads_carries_the_why_the_criteria_the_debt_and_the_signal(self) -> None:
        assert self._with_debt().rendered() == (
            "## Intencion\n"
            "sin esto el programa verifica y no entrega, asi que ningun run puede terminar\n"
            "\n"
            "## Criterios de aceptacion cumplidos\n"
            "- stagea exactamente las rutas declaradas por el implementador\n"
            "- nunca commitea en master ni en main\n"
            "\n"
            "## Deuda aceptada\n"
            "- el cableado del subcomando queda para la slice-09\n"
            "\n"
            "## Senal a comprobar tras el despliegue\n"
            "exenta - este repo no despliega\n"
            "\n"
            "Closes #46"
        )

    def test_a_slice_that_accepted_no_debt_leaves_the_section_out_instead_of_writing_none(self) -> None:
        assert self._without_debt().rendered() == (
            "## Intencion\n"
            "sin esto el programa verifica y no entrega, asi que ningun run puede terminar\n"
            "\n"
            "## Criterios de aceptacion cumplidos\n"
            "- stagea exactamente las rutas declaradas por el implementador\n"
            "- nunca commitea en master ni en main\n"
            "\n"
            "## Senal a comprobar tras el despliegue\n"
            "exenta - este repo no despliega\n"
            "\n"
            "Closes #46"
        )

    def test_the_reference_that_closes_the_subissue_is_the_last_thing_github_reads(self) -> None:
        assert self._with_debt().rendered().endswith("\nCloses #46")
        assert self._without_debt().rendered().endswith("\nCloses #46")

    def test_a_finding_the_judge_approved_without_correcting_names_the_rule_it_broke_not_only_its_elaboration(
        self,
    ) -> None:
        accepted = FindingMother.low_severity(path="src/y.py")
        body = PullRequestBody(
            intention=_INTENTION,
            criteria=_CRITERIA,
            debt=(),
            findings=(accepted,),
            signal=_SIGNAL,
            subissue=46,
        ).rendered()

        assert f"- {accepted.severity}: {accepted.rule} - {accepted.detail} ({accepted.path})" in body

    def test_a_finding_the_judge_approved_without_correcting_is_marked_apart_from_the_debt_the_implementer_declared(
        self,
    ) -> None:
        accepted = FindingMother.low_severity(path="src/y.py")
        body = PullRequestBody(
            intention=_INTENTION,
            criteria=_CRITERIA,
            debt=("el cableado del subcomando queda para la slice-09",),
            findings=(accepted,),
            signal=_SIGNAL,
            subissue=46,
        ).rendered()

        assert (
            "## Deuda aceptada\n"
            "- el cableado del subcomando queda para la slice-09\n"
            "\n"
            "Hallazgos que el juez dejo pasar sin corregir:\n"
            f"- {accepted.severity}: {accepted.rule} - {accepted.detail} ({accepted.path})\n"
            "\n"
            "## Senal a comprobar tras el despliegue"
        ) in body

    def test_a_finding_the_judge_approved_without_correcting_opens_the_debt_section_even_with_nothing_left_out(
        self,
    ) -> None:
        accepted = FindingMother.low_severity()
        body = PullRequestBody(
            intention=_INTENTION, criteria=_CRITERIA, debt=(), findings=(accepted,), signal=_SIGNAL, subissue=46
        ).rendered()

        assert "## Deuda aceptada" in body
