from __future__ import annotations

from slice_runner.infrastructure.understanding_comment import UnderstandingComment
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

_REPO = "alcaptar/agentic-skills"


class TestUnderstandingComment:
    def test_the_comment_says_which_slice_was_chosen_where_it_runs_and_the_whole_yardstick_it_will_be_measured_with(
        self,
    ) -> None:
        written = UnderstandingComment().write(
            subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls(), repo=_REPO
        )

        assert written == (
            "## Entendimiento de la slice\n"
            "\n"
            "slice-05 (prechecks-deterministas): comprobar antes de tocar codigo\n"
            "\n"
            "Es la primera del checklist que no esta cerrada, bloqueada ni abortada.\n"
            "\n"
            "- repo: alcaptar/agentic-skills\n"
            "- rama: slice/05-prechecks-deterministas\n"
            "\n"
            "### Intencion\n"
            "\n"
            "hoy nada evita reimplementar una slice ya entregada\n"
            "\n"
            "### Criterios de aceptacion\n"
            "\n"
            "- antes de tocar codigo comprueba que la subissue no este ya cerrada\n"
            "- cada precheck falla con un motivo distinguible, no con un booleano\n"
            "\n"
            "### Senal\n"
            "\n"
            "exenta - este repo no despliega\n"
            "\n"
            "### Fuentes de convencion\n"
            "\n"
            "- doc: CLAUDE.md\n"
            "\n"
            "### Controles del repo\n"
            "\n"
            "- lint: make linting\n"
        )

    def test_a_repo_exempt_from_controls_says_so_with_its_reason_instead_of_listing_none(self) -> None:
        written = UnderstandingComment().write(
            subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_exempt_controls(), repo=_REPO
        )

        assert written.endswith("### Controles del repo\n\n- ninguno: la integracion continua solo publica en master\n")
