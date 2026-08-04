from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.verify_slice import VerifySlice
from slice_runner.domain.diff_writer import DiffWriter
from slice_runner.domain.exceptions import DiffNotWrittenError
from slice_runner.domain.verifier import Verifier
from slice_runner.tests.mothers.verdict_mother import VerdictMother
from slice_runner.tests.mothers.verification_mother import (
    DiffOnDiskMother,
    VerifySliceParamsMother,
)

_DIFF = DiffOnDiskMother.inside(Path("/tmp/written-diff"), n_files=3)

_PARAMS = VerifySliceParamsMother.against_the_base()


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

    def test_the_judge_receives_the_diff_that_was_just_written_and_not_the_repo_and_base(
        self, writer: Mock, verifier: Mock
    ) -> None:
        VerifySlice(writer=writer, verifier=verifier).execute(_PARAMS)

        writer.write.assert_called_once_with(repo=_PARAMS.repo, base=_PARAMS.base)
        request = verifier.verify.call_args.args[0]
        assert request.diff is _DIFF
        assert request.repo == _PARAMS.repo
        assert request.instructions == _PARAMS.instructions

    def test_the_use_case_returns_the_judges_verdict_without_reinterpreting_it(
        self, writer: Mock, verifier: Mock
    ) -> None:
        expected = VerdictMother.failing()
        verifier.verify.return_value = expected

        verdict = VerifySlice(writer=writer, verifier=verifier).execute(_PARAMS)

        assert verdict is expected

    def test_with_no_diff_to_write_the_judge_is_not_invoked_at_all(self, writer: Mock, verifier: Mock) -> None:
        writer.write.side_effect = DiffNotWrittenError("nothing staged against master")

        with pytest.raises(DiffNotWrittenError):
            VerifySlice(writer=writer, verifier=verifier).execute(_PARAMS)

        verifier.verify.assert_not_called()
