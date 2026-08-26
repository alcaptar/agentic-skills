from __future__ import annotations

from slice_runner.infrastructure.conflict_resolver_brief import ConflictResolverBrief


class TestWhereTheSummaryFieldIsSpecified:
    def test_the_brief_does_not_respec_the_field_the_schema_already_describes(self) -> None:
        collapsed = " ".join(ConflictResolverBrief.TEXT.split()).lower()

        assert "para quien revise la conversacion" not in collapsed
        assert "no es una promesa de exito" not in collapsed

    def test_it_says_the_report_travels_in_a_single_field_because_a_second_one_is_what_the_harness_loses(
        self,
    ) -> None:
        collapsed = " ".join(ConflictResolverBrief.TEXT.split()).lower()

        assert "un solo campo" in collapsed
