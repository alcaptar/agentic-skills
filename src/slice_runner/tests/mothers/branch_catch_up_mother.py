from __future__ import annotations

from typing import ClassVar

from slice_runner.domain.branch_catch_up import BranchCatchUp


class BranchCatchUpMother:
    CONFLICTING_PATHS: ClassVar[tuple[str, ...]] = ("shared.txt",)

    @staticmethod
    def caught_up() -> BranchCatchUp:
        return BranchCatchUp.caught_up()

    @classmethod
    def conflicting_on_a_shared_file(cls) -> BranchCatchUp:
        return BranchCatchUp.conflicting(paths=cls.CONFLICTING_PATHS)

    @classmethod
    def conflicting_with_a_file_already_dirty_before_the_merge(cls, *, dirty: tuple[str, ...]) -> BranchCatchUp:
        return BranchCatchUp.conflicting(paths=cls.CONFLICTING_PATHS, dirty_before_merge=dirty)
