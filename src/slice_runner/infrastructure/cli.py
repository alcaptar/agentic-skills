from __future__ import annotations

import argparse
import json
import sys
from typing import TYPE_CHECKING

from slice_runner.application.actions.verify_slice import VerifySlice, VerifySliceParams
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.exceptions import (
    DiffNotReadableError,
    ImpossibleTransitionError,
    InvalidHarnessOutputError,
    UnreadableRunError,
    UnresolvableRepoOrBaseError,
)
from slice_runner.domain.state_machine import StateMachine
from slice_runner.infrastructure.claude_verifier import ClaudeVerifier
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.infrastructure.git_diff_reader import GitDiffReader
from slice_runner.infrastructure.local_corpus import LocalCorpus
from slice_runner.infrastructure.local_process import LocalProcess
from slice_runner.infrastructure.local_skill_library import LocalSkillLibrary
from slice_runner.infrastructure.process import ProcessNotRunnableError
from slice_runner.infrastructure.slice_verifier_judge import SliceVerifierJudge
from slice_runner.infrastructure.subcommand import Subcommand
from slice_runner.infrastructure.transition_payload import TransitionPayload
from slice_runner.infrastructure.transition_request_payload import TransitionRequestPayload
from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


class Cli:
    def __init__(self, *, process: Process) -> None:
        self._process = process

    @classmethod
    def main(cls, argv: list[str] | None = None) -> int:
        arguments = cls.parser().parse_args(argv)

        match Subcommand(arguments.command):
            case Subcommand.VERIFY:
                return cls(process=LocalProcess()).verify(
                    repo=arguments.repo, base=arguments.base, slice_id=arguments.slice_id
                )
            case Subcommand.EXPLAIN:
                return cls.explain(request=sys.stdin.read())

    @classmethod
    def parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="python -m slice_runner",
            description="Slice orchestrator. See `docs/superpowers/specs/` for the design.",
        )
        subcommands = parser.add_subparsers(dest="command", required=True)

        verify = subcommands.add_parser(Subcommand.VERIFY, help="judge the index of a slice against its base")
        verify.add_argument("--repo", required=True, help="path of the slice's repo")
        verify.add_argument("--base", required=True, help="base branch the diff is taken against")
        verify.add_argument(
            "--slice", dest="slice_id", required=True, help="identifier of the slice the verdict belongs to"
        )

        subcommands.add_parser(
            Subcommand.EXPLAIN, help="say what comes after the run and the outcome read on standard input"
        )

        return parser

    @classmethod
    def explain(cls, *, request: str) -> int:
        try:
            asked = TransitionRequestPayload.read(request)
            transition = StateMachine(budgets=Budgets()).after(asked.run.to_domain(), asked.outcome)
        except (ImpossibleTransitionError, UnreadableRunError) as error:
            return cls._reported(f"there is no transition to explain: {error}", ExitCode.USAGE_ERROR)

        print(json.dumps(TransitionPayload.from_domain(transition).to_contract(), ensure_ascii=False))

        return ExitCode.OK

    def verify(self, *, repo: str, base: str, slice_id: str) -> int:
        try:
            verification = self._action().execute(self._params(repo=repo, base=base, slice_id=slice_id))
        except UnresolvableRepoOrBaseError as error:
            return self._reported(f"the repo or the base requested do not resolve: {error}", ExitCode.USAGE_ERROR)
        except DiffNotReadableError as error:
            return self._reported(f"there is no diff to verify: {error}", ExitCode.NO_DIFF)
        except InvalidHarnessOutputError as error:
            return self._reported(f"the judge left no usable verdict: {error}", ExitCode.NO_USABLE_VERDICT)
        except ProcessNotRunnableError as error:
            return self._reported(
                f"a process the run needs could not be launched, so there is no verdict: {error}",
                ExitCode.NO_USABLE_VERDICT,
            )

        self._warn_about(verification.denied_reads)
        print(json.dumps(VerdictPayload.from_domain(verification.verdict).to_contract(), ensure_ascii=False))

        return ExitCode.of(verification.verdict.ruling)

    def _action(self) -> VerifySlice:
        return VerifySlice(
            reader=GitDiffReader(process=self._process),
            verifier=ClaudeVerifier(process=self._process),
            judge=SliceVerifierJudge.adversarial(),
            skills=LocalSkillLibrary(),
            corpus=LocalCorpus(),
        )

    @staticmethod
    def _warn_about(denied_reads: tuple[str, ...]) -> None:
        if not denied_reads:
            return

        print(
            f"the judge was denied {len(denied_reads)} read(s), so it may have measured with an incomplete "
            f"yardstick: {', '.join(denied_reads)}",
            file=sys.stderr,
        )

    @staticmethod
    def _params(*, repo: str, base: str, slice_id: str) -> VerifySliceParams:
        return VerifySliceParams(
            repo=repo, base=base, slice_id=slice_id, signal="", criteria=(), sources=(), checklist=()
        )

    @staticmethod
    def _reported(reason: str, code: ExitCode) -> ExitCode:
        print(reason, file=sys.stderr)

        return code
