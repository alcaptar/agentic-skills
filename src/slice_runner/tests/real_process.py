from __future__ import annotations

from slice_runner.domain.budgets import Budgets
from slice_runner.infrastructure.local_process import LocalProcess


class Real:
    @staticmethod
    def process() -> LocalProcess:
        return LocalProcess(budgets=Budgets())
