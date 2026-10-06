from __future__ import annotations

import json

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import Answer, AnsweringByArgv
from slice_runner.tests.mothers.gh_conversation_mother import GhConversationMother
from slice_runner.tests.mothers.run_mother import RunMother

_REPO = GhConversationMother.REPO
_ISSUE = GhConversationMother.SUBISSUE
_TOKENS = ("-GO", "-REVIEW", "-RETRY")


class _Orders:
    @staticmethod
    def process(view: dict[str, object]) -> AnsweringByArgv:
        body = view["body"]
        assert isinstance(body, str)

        return AnsweringByArgv(
            Answer(to=("view", "--json", "number,title,body,labels,state"), stdout=json.dumps(view)),
            Answer(to=("view", "--json", "body"), stdout=json.dumps({"body": body})),
            Answer(to=("edit", "--body-file")),
            Answer(to=("edit", "--add-label")),
            Answer(to=("comment",)),
        )

    @staticmethod
    def awaiting_alignment() -> dict[str, object]:
        return GhConversationMother.the_subissue_viewed(
            label=IssueLabel.AWAITING_ALIGNMENT, run=RunMother.awaiting_alignment()
        )

    @staticmethod
    def blocked_on_red_ci() -> dict[str, object]:
        return GhConversationMother.the_subissue_viewed(
            label=IssueLabel.BLOCKED_CI_RED, run=RunMother.blocked_on_red_ci()
        )

    @staticmethod
    def written_block(process: AnsweringByArgv) -> dict[str, object]:
        rewritten = next(call for call in process.calls if "--body-file" in call.argv)
        raw = rewritten.stdin.split("<!-- slice-runner:estado\n", maxsplit=1)[1].split("\n-->", maxsplit=1)[0]
        block = json.loads(raw)
        assert isinstance(block, dict)

        return block

    @staticmethod
    def left_comment(process: AnsweringByArgv) -> str:
        return next(call.stdin for call in process.calls if "comment" in call.argv)

    @staticmethod
    def wrote_nothing(process: AnsweringByArgv) -> bool:
        return not any("edit" in call.argv or "comment" in call.argv for call in process.calls)

    @staticmethod
    def only_talked_to_github(process: AnsweringByArgv) -> bool:
        return all(call.argv[0] == "gh" for call in process.calls)


class TestGo(_Orders):
    def test_it_saves_the_agreement_in_the_run_and_exits_with_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        process = self.process(self.awaiting_alignment())

        code = Cli(process=process, budgets=Budgets()).go(repo=_REPO, issue=_ISSUE)

        assert code == ExitCode.OK
        assert self.written_block(process)["alignment"] == "agreed"

    def test_it_leaves_a_comment_saying_which_order_was_given_without_any_token(self) -> None:
        process = self.process(self.awaiting_alignment())

        Cli(process=process, budgets=Budgets()).go(repo=_REPO, issue=_ISSUE)

        comment = self.left_comment(process)
        assert "`go`" in comment
        assert not any(token in comment for token in _TOKENS)

    def test_it_never_launches_the_run_or_the_model(self) -> None:
        process = self.process(self.awaiting_alignment())

        Cli(process=process, budgets=Budgets()).go(repo=_REPO, issue=_ISSUE)

        assert self.only_talked_to_github(process)
        assert not process.invoked("worktree")

    @pytest.mark.parametrize(
        "view",
        [
            GhConversationMother.the_subissue_viewed(label=IssueLabel.PENDING),
            GhConversationMother.the_subissue_viewed(label=IssueLabel.IN_PROGRESS, run=RunMother.implementing()),
            GhConversationMother.the_subissue_viewed(
                label=IssueLabel.AWAITING_ALIGNMENT, run=RunMother.with_the_understanding_agreed()
            ),
            GhConversationMother.the_subissue_viewed(
                label=IssueLabel.AWAITING_ALIGNMENT, run=RunMother.about_to_publish_the_understanding()
            ),
            GhConversationMother.the_subissue_viewed(
                label=IssueLabel.BLOCKED_CI_RED, run=RunMother.blocked_on_red_ci()
            ),
        ],
    )
    def test_a_slice_that_is_not_waiting_for_alignment_is_refused_with_its_own_code_and_writes_nothing(
        self, view: dict[str, object], capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = self.process(view)

        code = Cli(process=process, budgets=Budgets()).go(repo=_REPO, issue=_ISSUE)

        captured = capsys.readouterr()
        assert code == ExitCode.ORDER_REFUSED
        assert "not waiting for the alignment" in captured.err
        assert captured.out == ""
        assert self.wrote_nothing(process)


class TestReview(_Orders):
    def test_it_saves_the_correction_in_the_run_and_sends_the_understanding_back_to_be_drafted(self) -> None:
        process = self.process(self.awaiting_alignment())

        code = Cli(process=process, budgets=Budgets()).review(repo=_REPO, issue=_ISSUE, correction="falta la senal")

        block = self.written_block(process)
        assert code == ExitCode.OK
        assert (block["corrected"], block["alignment"]) == ("falta la senal", "draft")

    def test_a_second_review_leaves_only_the_second_correction(self) -> None:
        reviewed = GhConversationMother.the_subissue_viewed(
            label=IssueLabel.AWAITING_ALIGNMENT, run=RunMother.about_to_redraft_after_a_correction("la primera")
        )
        process = self.process(reviewed)

        Cli(process=process, budgets=Budgets()).review(repo=_REPO, issue=_ISSUE, correction="la segunda")

        rewritten = next(call.stdin for call in process.calls if "--body-file" in call.argv)
        assert self.written_block(process)["corrected"] == "la segunda"
        assert "la primera" not in rewritten

    def test_it_leaves_a_comment_with_the_text_and_without_any_token(self) -> None:
        process = self.process(self.awaiting_alignment())

        Cli(process=process, budgets=Budgets()).review(repo=_REPO, issue=_ISSUE, correction="falta la senal")

        comment = self.left_comment(process)
        assert "`review`" in comment
        assert "falta la senal" in comment
        assert not any(token in comment for token in _TOKENS)

    def test_it_never_launches_the_run_or_the_model(self) -> None:
        process = self.process(self.awaiting_alignment())

        Cli(process=process, budgets=Budgets()).review(repo=_REPO, issue=_ISSUE, correction="x")

        assert self.only_talked_to_github(process)

    def test_a_slice_that_is_not_waiting_for_alignment_is_refused_with_its_own_code_and_writes_nothing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = self.process(GhConversationMother.the_subissue_viewed(label=IssueLabel.PENDING))

        code = Cli(process=process, budgets=Budgets()).review(repo=_REPO, issue=_ISSUE, correction="x")

        captured = capsys.readouterr()
        assert code == ExitCode.ORDER_REFUSED
        assert "not waiting for the alignment" in captured.err
        assert self.wrote_nothing(process)

    def test_a_blank_correction_is_a_usage_error_that_does_not_even_read_the_issue(self) -> None:
        process = self.process(self.awaiting_alignment())

        code = Cli(process=process, budgets=Budgets()).review(repo=_REPO, issue=_ISSUE, correction="  ")

        assert code == ExitCode.USAGE_ERROR
        assert process.calls == []


class TestRetry(_Orders):
    def test_it_reopens_the_slice_by_its_label_and_resets_the_counter_that_blocked_it(self) -> None:
        process = self.process(self.blocked_on_red_ci())

        code = Cli(process=process, budgets=Budgets()).retry(repo=_REPO, issue=_ISSUE, instruction="ya esta a mano")

        edit = next(call for call in process.calls if "--add-label" in call.argv)
        block = self.written_block(process)
        assert code == ExitCode.OK
        assert Argv(edit.argv).value_of("--remove-label") == IssueLabel.BLOCKED_CI_RED.value
        assert Argv(edit.argv).value_of("--add-label") == IssueLabel.IN_PROGRESS.value
        assert block["ci_retries"] == 0

    def test_it_saves_the_instruction_in_the_run_so_a_process_that_dies_cannot_lose_it(self) -> None:
        process = self.process(self.blocked_on_red_ci())

        Cli(process=process, budgets=Budgets()).retry(repo=_REPO, issue=_ISSUE, instruction="ya esta a mano")

        assert self.written_block(process)["retry_instruction"] == "ya esta a mano"

    def test_it_leaves_a_comment_with_the_text_and_without_any_token(self) -> None:
        process = self.process(self.blocked_on_red_ci())

        Cli(process=process, budgets=Budgets()).retry(repo=_REPO, issue=_ISSUE, instruction="ya esta a mano")

        comment = self.left_comment(process)
        assert "`retry`" in comment
        assert "ya esta a mano" in comment
        assert not any(token in comment for token in _TOKENS)

    def test_it_never_launches_the_run_or_the_model(self) -> None:
        process = self.process(self.blocked_on_red_ci())

        Cli(process=process, budgets=Budgets()).retry(repo=_REPO, issue=_ISSUE, instruction="x")

        assert self.only_talked_to_github(process)

    @pytest.mark.parametrize(
        "view",
        [
            GhConversationMother.the_subissue_viewed(label=IssueLabel.PENDING),
            GhConversationMother.the_subissue_viewed(label=IssueLabel.IN_PROGRESS, run=RunMother.implementing()),
            GhConversationMother.the_subissue_viewed(
                label=IssueLabel.AWAITING_ALIGNMENT, run=RunMother.awaiting_alignment()
            ),
        ],
    )
    def test_a_slice_that_is_neither_blocked_nor_aborted_is_refused_with_its_own_code_and_writes_nothing(
        self, view: dict[str, object], capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = self.process(view)

        code = Cli(process=process, budgets=Budgets()).retry(repo=_REPO, issue=_ISSUE, instruction="x")

        captured = capsys.readouterr()
        assert code == ExitCode.ORDER_REFUSED
        assert "neither blocked nor aborted" in captured.err
        assert self.wrote_nothing(process)


class TestTheParserOfTheOrders:
    def test_review_takes_the_text_after_the_options_as_several_words(self) -> None:
        arguments = Cli.parser().parse_args(["review", "45", "--repo", _REPO, "falta", "la", "senal"])

        assert (arguments.issue, arguments.repo, arguments.text) == (45, _REPO, ["falta", "la", "senal"])

    def test_retry_takes_the_text_after_the_options_as_several_words(self) -> None:
        arguments = Cli.parser().parse_args(["retry", "45", "--repo", _REPO, "ya", "esta"])

        assert arguments.text == ["ya", "esta"]

    @pytest.mark.parametrize("subcommand", ["review", "retry"])
    def test_the_text_is_required(self, subcommand: str, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args([subcommand, "45", "--repo", _REPO])

        assert "text" in capsys.readouterr().err

    @pytest.mark.parametrize("subcommand", ["go", "review", "retry"])
    def test_the_repo_is_required(self, subcommand: str, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args([subcommand, "45", "texto"])

        assert "--repo" in capsys.readouterr().err

    def test_go_takes_no_text(self) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(["go", "45", "--repo", _REPO, "texto"])


class TestARunBlockWrittenByAnEarlierVersion(_Orders):
    @staticmethod
    def _stale() -> dict[str, object]:
        return GhConversationMother.the_subissue_viewed(
            label=IssueLabel.AWAITING_ALIGNMENT, run=RunMother.awaiting_alignment(), stale=True
        )

    @pytest.mark.parametrize("order", ["go", "review", "retry"])
    def test_every_order_names_the_reset_command_and_writes_nothing(
        self, order: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = self.process(self._stale())
        cli = Cli(process=process, budgets=Budgets())
        orders = {
            "go": lambda: cli.go(repo=_REPO, issue=_ISSUE),
            "review": lambda: cli.review(repo=_REPO, issue=_ISSUE, correction="x"),
            "retry": lambda: cli.retry(repo=_REPO, issue=_ISSUE, instruction="x"),
        }

        code = orders[order]()

        assert code == ExitCode.USAGE_ERROR
        assert f"slice-runner reset {_ISSUE} --repo {_REPO}" in capsys.readouterr().err
        assert self.wrote_nothing(process)

    def test_reset_clears_that_block_instead_of_refusing_to_read_it(self, capsys: pytest.CaptureFixture[str]) -> None:
        process = self.process(self._stale())

        code = Cli(process=process, budgets=Budgets()).reset(repo=_REPO, issue=_ISSUE)

        rewritten = next(call for call in process.calls if "--body-file" in call.argv)
        assert code == ExitCode.OK
        assert "slice-runner:estado" not in rewritten.stdin
