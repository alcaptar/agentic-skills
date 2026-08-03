from __future__ import annotations

from pathlib import Path
from unittest.mock import create_autospec

import pytest

from slice_runner.application.verify_slice import VerifySlice, VerifySliceParams
from slice_runner.domain.diff import DiffBundler, DiffNotBundlableError, SliceDiff
from slice_runner.domain.verdict import Ruling, Verdict
from slice_runner.domain.verification import Verifier

_DIFF = SliceDiff(slice_diff=Path("/tmp/b/slice.diff"), files=Path("/tmp/b/files.txt"), n_files=3)

_PARAMS = VerifySliceParams(
    repo="/repos/project",
    base="master",
    instructions="You are the adversarial verifier.",
)


def test_the_judge_receives_the_bundle_that_was_just_packed_and_not_the_repo_and_base() -> None:
    bundler = create_autospec(DiffBundler, spec_set=True, instance=True)
    bundler.bundle.return_value = _DIFF
    verifier = create_autospec(Verifier, spec_set=True, instance=True)
    verifier.verify.return_value = Verdict(ruling=Ruling.PASS)

    VerifySlice(bundler=bundler, verifier=verifier).execute(_PARAMS)

    bundler.bundle.assert_called_once_with(repo="/repos/project", base="master")
    request = verifier.verify.call_args.args[0]
    assert request.diff is _DIFF
    assert request.repo == "/repos/project"
    assert request.instructions == "You are the adversarial verifier."


def test_the_use_case_returns_the_judges_verdict_without_reinterpreting_it() -> None:
    bundler = create_autospec(DiffBundler, spec_set=True, instance=True)
    bundler.bundle.return_value = _DIFF
    verifier = create_autospec(Verifier, spec_set=True, instance=True)
    expected = Verdict(ruling=Ruling.FAIL)
    verifier.verify.return_value = expected

    verdict = VerifySlice(bundler=bundler, verifier=verifier).execute(_PARAMS)

    assert verdict is expected


def test_with_no_diff_to_bundle_the_judge_is_not_invoked_at_all() -> None:
    bundler = create_autospec(DiffBundler, spec_set=True, instance=True)
    bundler.bundle.side_effect = DiffNotBundlableError("nothing staged against master")
    verifier = create_autospec(Verifier, spec_set=True, instance=True)

    with pytest.raises(DiffNotBundlableError):
        VerifySlice(bundler=bundler, verifier=verifier).execute(_PARAMS)

    verifier.verify.assert_not_called()
