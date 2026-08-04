from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.application.actions.verify_slice import VerifySliceParams
from slice_runner.domain.diff_on_disk import DiffOnDisk
from slice_runner.domain.verification_request import VerificationRequest

if TYPE_CHECKING:
    from pathlib import Path


class DiffOnDiskMother:
    @staticmethod
    def inside(directory: Path, *, n_files: int = 2) -> DiffOnDisk:
        return DiffOnDisk(diff=directory / "slice.diff", files=directory / "files.txt", n_files=n_files)


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
    def with_the_diff_in(cls, directory: Path, *, repo: str | None = None) -> VerificationRequest:
        return VerificationRequest(
            repo=repo or cls.REPO,
            instructions=cls.INSTRUCTIONS,
            diff=DiffOnDiskMother.inside(directory),
        )
