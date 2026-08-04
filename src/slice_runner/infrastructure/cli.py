from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from slice_runner.application.actions.verify_slice import VerifySlice, VerifySliceParams
from slice_runner.domain.exceptions import (
    DiffNotWrittenError,
    InvalidVerdictError,
    UnresolvableRepoOrBaseError,
)
from slice_runner.infrastructure.claude_verifier import ClaudeVerifier
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.infrastructure.git_diff_writer import GitDiffWriter
from slice_runner.infrastructure.local_process import LocalProcess
from slice_runner.infrastructure.process import ProcessNotRunnableError
from slice_runner.infrastructure.slice_verifier_prompt import SliceVerifierPrompt
from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


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
        except DiffNotWrittenError as error:
            return self._reported(f"there is no diff to verify: {error}", ExitCode.NO_DIFF)
        except InvalidVerdictError as error:
            return self._reported(f"the judge left no usable verdict: {error}", ExitCode.NO_USABLE_VERDICT)
        except ProcessNotRunnableError as error:
            return self._reported(
                f"a process the run needs could not be launched, so there is no verdict: {error}",
                ExitCode.NO_USABLE_VERDICT,
            )

        print(json.dumps(VerdictPayload.from_domain(verdict).to_contract(), ensure_ascii=False))

        return ExitCode.of(verdict.ruling)

    def _action(self) -> VerifySlice:
        return VerifySlice(
            writer=GitDiffWriter(process=self._process, destination=self._destination_outside_the_repo()),
            verifier=ClaudeVerifier(process=self._process),
            prompt_provider=SliceVerifierPrompt(),
        )

    @staticmethod
    def _params(*, repo: str, base: str) -> VerifySliceParams:
        return VerifySliceParams(repo=repo, base=base)

    @staticmethod
    def _destination_outside_the_repo() -> Path:
        return Path(tempfile.mkdtemp(prefix="slice-runner-"))

    @staticmethod
    def _reported(reason: str, code: ExitCode) -> ExitCode:
        print(reason, file=sys.stderr)

        return code
