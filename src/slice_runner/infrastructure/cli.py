from __future__ import annotations

import argparse
import json
import sys
import tempfile
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING

from slice_runner.application.verify_slice import VerifySlice, VerifySliceParams
from slice_runner.domain.diff import DiffNotBundlableError, UnresolvableRepoOrBaseError
from slice_runner.domain.verdict import InvalidVerdictError, Ruling
from slice_runner.infrastructure.diff import GitDiffBundler
from slice_runner.infrastructure.payloads import VerdictPayload
from slice_runner.infrastructure.process import LocalProcess, ProcessNotRunnableError
from slice_runner.infrastructure.prompt import AgentPrompt
from slice_runner.infrastructure.verifier import ClaudeVerifier

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


class ExitCode(IntEnum):
    PASS = 0
    FAIL = 1
    NO_USABLE_VERDICT = 2
    NO_DIFF = 3
    USAGE_ERROR = 4

    @classmethod
    def of(cls, ruling: Ruling) -> ExitCode:
        match ruling:
            case Ruling.PASS:
                return cls.PASS
            case Ruling.FAIL:
                return cls.FAIL


class Cli:
    def __init__(self, *, process: Process) -> None:
        self._process = process

    @classmethod
    def main(cls, argv: list[str] | None = None) -> int:
        arguments = cls.parser().parse_args(argv)

        return cls(process=LocalProcess()).verify(repo=arguments.repo, base=arguments.base)

    @classmethod
    def parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="python -m slice_runner",
            description="Slice orchestrator. See `docs/superpowers/specs/` for the design.",
        )
        subcommands = parser.add_subparsers(dest="command", required=True)

        verify = subcommands.add_parser("verify", help="judge the index of a slice against its base")
        verify.add_argument("--repo", required=True, help="path of the slice's repo")
        verify.add_argument("--base", required=True, help="base branch the diff is taken against")

        return parser

    def verify(self, *, repo: str, base: str) -> int:
        try:
            verdict = self._action().execute(self._params(repo=repo, base=base))
        except UnresolvableRepoOrBaseError as error:
            return self._reported(f"the repo or the base requested do not resolve: {error}", ExitCode.USAGE_ERROR)
        except DiffNotBundlableError as error:
            return self._reported(f"there is no diff to verify: {error}", ExitCode.NO_DIFF)
        except InvalidVerdictError as error:
            return self._reported(f"the judge left no usable verdict: {error}", ExitCode.NO_USABLE_VERDICT)
        except ProcessNotRunnableError as error:
            return self._reported(
                f"the judge could not be launched, so there is no verdict: {error}", ExitCode.NO_USABLE_VERDICT
            )

        print(json.dumps(VerdictPayload.from_domain(verdict).to_contract(), ensure_ascii=False))

        return ExitCode.of(verdict.ruling)

    def _action(self) -> VerifySlice:
        return VerifySlice(
            bundler=GitDiffBundler(destination=self._bundle_destination_outside_the_repo()),
            verifier=ClaudeVerifier(process=self._process),
        )

    @staticmethod
    def _params(*, repo: str, base: str) -> VerifySliceParams:
        return VerifySliceParams(repo=repo, base=base, instructions=AgentPrompt.read(AgentPrompt.JUDGE))

    @staticmethod
    def _bundle_destination_outside_the_repo() -> Path:
        return Path(tempfile.mkdtemp(prefix="slice-runner-"))

    @staticmethod
    def _reported(reason: str, code: ExitCode) -> ExitCode:
        print(reason, file=sys.stderr)

        return code
