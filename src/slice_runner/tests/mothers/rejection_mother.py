from __future__ import annotations

from slice_runner.domain.exceptions import InvalidHarnessOutputError, InvalidVerdictError, PermissionDeniedError
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother


class RejectionMother:
    @staticmethod
    def incoherent_verdict() -> InvalidVerdictError:
        rejection = InvalidVerdictError("a PASA with a finding of severity alta contradicts the rubric")
        rejection.spend = HarnessSpendMother.of_the_judge_call()

        return rejection

    @staticmethod
    def denied_read() -> PermissionDeniedError:
        rejection = PermissionDeniedError("the judge was denied reading the diff")
        rejection.spend = HarnessSpendMother.of_the_judge_call()

        return rejection

    @staticmethod
    def envelope_nobody_could_parse() -> InvalidHarnessOutputError:
        return InvalidHarnessOutputError("the harness returned no JSON (code 1): claude: command not found")
