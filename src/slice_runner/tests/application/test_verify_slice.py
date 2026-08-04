from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.verify_slice import VerifySlice
from slice_runner.domain.diff import DiffBundler, DiffNotBundlableError
from slice_runner.domain.verification import Verifier
from slice_runner.tests.mothers.verdict_mother import VerdictMother
from slice_runner.tests.mothers.verification_mother import (
    SliceDiffMother,
    VerifySliceParamsMother,
)

_DIFF = SliceDiffMother.inside(Path("/tmp/bundle"), n_files=3)

_PARAMS = VerifySliceParamsMother.against_the_base()


class TestVerifySlice:
    @pytest.fixture
    def bundler(self) -> Mock:
        bundler: Mock = create_autospec(DiffBundler, spec_set=True, instance=True)
        bundler.bundle.return_value = _DIFF
        return bundler

    @pytest.fixture
    def verifier(self) -> Mock:
        verifier: Mock = create_autospec(Verifier, spec_set=True, instance=True)
        verifier.verify.return_value = VerdictMother.passing()
        return verifier

    def test_the_judge_receives_the_bundle_that_was_just_packed_and_not_the_repo_and_base(
        self, bundler: Mock, verifier: Mock
    ) -> None:
        VerifySlice(bundler=bundler, verifier=verifier).execute(_PARAMS)

        bundler.bundle.assert_called_once_with(repo=_PARAMS.repo, base=_PARAMS.base)
        request = verifier.verify.call_args.args[0]
        assert request.diff is _DIFF
        assert request.repo == _PARAMS.repo
        assert request.instructions == _PARAMS.instructions

    def test_the_use_case_returns_the_judges_verdict_without_reinterpreting_it(
        self, bundler: Mock, verifier: Mock
    ) -> None:
        expected = VerdictMother.failing()
        verifier.verify.return_value = expected

        verdict = VerifySlice(bundler=bundler, verifier=verifier).execute(_PARAMS)

        assert verdict is expected

    def test_with_no_diff_to_bundle_the_judge_is_not_invoked_at_all(self, bundler: Mock, verifier: Mock) -> None:
        bundler.bundle.side_effect = DiffNotBundlableError("nothing staged against master")

        with pytest.raises(DiffNotBundlableError):
            VerifySlice(bundler=bundler, verifier=verifier).execute(_PARAMS)

        verifier.verify.assert_not_called()
