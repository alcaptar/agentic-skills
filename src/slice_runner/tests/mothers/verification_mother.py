from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.application.verify_slice import VerifySliceParams
from slice_runner.domain.diff import SliceDiff
from slice_runner.domain.verification import VerificationRequest

if TYPE_CHECKING:
    from pathlib import Path


class SliceDiffMother:
    @staticmethod
    def inside(bundle: Path, *, n_files: int = 2) -> SliceDiff:
        return SliceDiff(slice_diff=bundle / "slice.diff", files=bundle / "files.txt", n_files=n_files)


class VerifySliceParamsMother:
    BASE: ClassVar[str] = "master"

    @classmethod
    def against_the_base(cls) -> VerifySliceParams:
        return VerifySliceParams(
            repo=VerificationRequestMother.REPO,
            base=cls.BASE,
            instructions=VerificationRequestMother.INSTRUCTIONS,
        )


class VerificationRequestMother:
    REPO: ClassVar[str] = "/repos/project"
    INSTRUCTIONS: ClassVar[str] = "You are the adversarial verifier."

    @classmethod
    def with_the_bundle_in(cls, bundle: Path, *, repo: str | None = None) -> VerificationRequest:
        return VerificationRequest(
            repo=repo or cls.REPO,
            instructions=cls.INSTRUCTIONS,
            diff=SliceDiffMother.inside(bundle),
        )
