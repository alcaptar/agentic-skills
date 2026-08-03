from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from slice_runner.application.verify_slice import VerifySlice, VerifySliceParams
from slice_runner.domain.diff import DiffNotBundlableError, UnresolvableRepoOrBaseError
from slice_runner.domain.verdict import InvalidVerdictError, Ruling
from slice_runner.infrastructure.diff import GitDiffBundler
from slice_runner.infrastructure.process import LocalProcess, Process, ProcessNotRunnableError
from slice_runner.infrastructure.prompt import JUDGE_PROMPT_PATH, read_agent_prompt
from slice_runner.infrastructure.verifier import ClaudeVerifier

EXIT_BY_RULING = {Ruling.PASS: 0, Ruling.FAIL: 1}
EXIT_NO_USABLE_VERDICT = 2
EXIT_NO_DIFF = 3
EXIT_USAGE_ERROR = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m slice_runner",
        description="Slice orchestrator. See `docs/superpowers/specs/` for the design.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify", help="judge the index of a slice against its base")
    verify.add_argument("--repo", required=True, help="path of the slice's repo")
    verify.add_argument("--base", required=True, help="base branch the diff is taken against")
    return parser


def _bundle_destination_outside_the_repo() -> Path:
    return Path(tempfile.mkdtemp(prefix="slice-runner-"))


def run_verify(*, repo: str, base: str, process: Process) -> int:
    action = VerifySlice(
        bundler=GitDiffBundler(destination=_bundle_destination_outside_the_repo()),
        verifier=ClaudeVerifier(process=process),
    )
    params = VerifySliceParams(
        repo=repo,
        base=base,
        instructions=read_agent_prompt(JUDGE_PROMPT_PATH),
    )
    try:
        verdict = action.execute(params)
    except UnresolvableRepoOrBaseError as exc:
        print(f"the repo or the base requested do not resolve: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    except DiffNotBundlableError as exc:
        print(f"there is no diff to verify: {exc}", file=sys.stderr)
        return EXIT_NO_DIFF
    except InvalidVerdictError as exc:
        print(f"the judge left no usable verdict: {exc}", file=sys.stderr)
        return EXIT_NO_USABLE_VERDICT
    except ProcessNotRunnableError as exc:
        print(f"the judge could not be launched, so there is no verdict: {exc}", file=sys.stderr)
        return EXIT_NO_USABLE_VERDICT

    print(json.dumps(verdict.to_dict(), ensure_ascii=False))
    return EXIT_BY_RULING[verdict.ruling]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_verify(repo=args.repo, base=args.base, process=LocalProcess())
