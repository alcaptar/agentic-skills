from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.verify_slice import VerifySlice
from slice_runner.domain.diff_writer import DiffWriter
from slice_runner.domain.exceptions import DiffNotWrittenError
from slice_runner.domain.prompt_provider import PromptProvider
from slice_runner.domain.verifier import Verifier
from slice_runner.tests.mothers.verdict_mother import VerdictMother
from slice_runner.tests.mothers.verification_mother import DiffOnDiskMother, VerifySliceParamsMother

_DIFF = DiffOnDiskMother.written_in(Path("/tmp/written-diff"), files=("src/a.py", "src/tests/test_a.py"))

_PARAMS = VerifySliceParamsMother.against_the_base()

_RUBRIC = "You are the adversarial verifier. Walk the closed rubric."


class TestVerifySlice:
    @pytest.fixture
    def writer(self) -> Mock:
        writer: Mock = create_autospec(DiffWriter, spec_set=True, instance=True)
        writer.write.return_value = _DIFF
        return writer

    @pytest.fixture
    def verifier(self) -> Mock:
        verifier: Mock = create_autospec(Verifier, spec_set=True, instance=True)
        verifier.verify.return_value = VerdictMother.passing()
        return verifier

    @pytest.fixture
    def prompt_provider(self) -> Mock:
        provider: Mock = create_autospec(PromptProvider, spec_set=True, instance=True)
        provider.system_template.return_value = _RUBRIC
        return provider

    @pytest.fixture
    def action(self, writer: Mock, verifier: Mock, prompt_provider: Mock) -> VerifySlice:
        return VerifySlice(writer=writer, verifier=verifier, prompt_provider=prompt_provider)

    def test_the_diff_is_written_for_the_repo_and_base_that_were_asked_for(
        self, action: VerifySlice, writer: Mock
    ) -> None:
        action.execute(_PARAMS)

        writer.write.assert_called_once_with(repo=_PARAMS.repo, base=_PARAMS.base)

    def test_the_judge_gets_the_diff_that_was_just_written_and_not_the_repo_and_base(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        action.execute(_PARAMS)

        assert verifier.verify.call_args.args[0].diff is _DIFF

    def test_the_prompt_opens_with_the_rubric_the_provider_gave_and_not_with_the_run_data(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        action.execute(_PARAMS)

        text = verifier.verify.call_args.args[0].build()
        assert text.startswith(_RUBRIC)
        assert text.index("## Datos del run") > text.index(_RUBRIC)

    def test_the_prompt_carries_the_repo_and_where_the_diff_was_written(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        text = self._prompt_of(action, verifier)

        assert _PARAMS.repo in text
        assert str(_DIFF.diff) in text

    def test_the_prompt_carries_the_scope_so_it_does_not_depend_on_the_judge_opening_a_file(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        text = self._prompt_of(action, verifier)

        assert "src/a.py" in text
        assert "src/tests/test_a.py" in text

    def test_the_count_of_files_is_derived_from_the_list_so_it_cannot_disagree_with_it(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        assert f"({len(_DIFF.files)})" in self._prompt_of(action, verifier)

    def test_the_verdict_comes_back_without_being_reinterpreted(self, action: VerifySlice, verifier: Mock) -> None:
        expected = VerdictMother.failing()
        verifier.verify.return_value = expected

        assert action.execute(_PARAMS) is expected

    def test_with_no_diff_to_write_the_judge_is_not_invoked_at_all(
        self, action: VerifySlice, writer: Mock, verifier: Mock
    ) -> None:
        writer.write.side_effect = DiffNotWrittenError("nothing staged against master")

        with pytest.raises(DiffNotWrittenError):
            action.execute(_PARAMS)

        verifier.verify.assert_not_called()

    @staticmethod
    def _prompt_of(action: VerifySlice, verifier: Mock) -> str:
        action.execute(_PARAMS)

        text: str = verifier.verify.call_args.args[0].build()
        return text
