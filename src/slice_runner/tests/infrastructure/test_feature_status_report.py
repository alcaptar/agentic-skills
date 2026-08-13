from __future__ import annotations

from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.slice_status import SliceStatus
from slice_runner.domain.step import Step
from slice_runner.infrastructure.feature_status_report import FeatureStatusReport
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother


class TestFeatureStatusReport:
    def test_each_slice_appears_on_its_own_line_with_its_identifier_and_its_label(self) -> None:
        statuses = (
            SliceStatus(sub_issue=SubIssueMother.pending(), pull_request=None),
            SliceStatus(sub_issue=SubIssueMother.of_another_repo(), pull_request=None),
        )

        rendered = FeatureStatusReport(statuses=statuses).rendered()

        assert len(rendered.splitlines()) == 2
        assert SubIssueMother.pending().slice_id in rendered
        assert IssueLabel.PENDING.value in rendered

    def test_a_slice_that_carries_no_label_prints_the_state_of_the_issue_instead(self) -> None:
        status = SliceStatus(sub_issue=SubIssueMother.unlabelled(), pull_request=None)

        rendered = FeatureStatusReport(statuses=(status,)).rendered()

        assert IssueState.OPEN.value in rendered

    def test_a_slice_that_never_started_shows_no_step_and_no_spend_instead_of_a_zero(self) -> None:
        status = SliceStatus(sub_issue=SubIssueMother.pending(), pull_request=None)

        rendered = FeatureStatusReport(statuses=(status,)).rendered()

        assert "$" not in rendered
        assert not any(step.value in rendered for step in Step)

    def test_a_slice_with_a_run_shows_the_step_it_is_on(self) -> None:
        status = SliceStatus(
            sub_issue=SubIssueMother.blocked(IssueLabel.BLOCKED_CI_RED, RunMother.blocked_on_red_ci()),
            pull_request=None,
        )

        rendered = FeatureStatusReport(statuses=(status,)).rendered()

        assert Step.AWAIT_CI.value in rendered

    def test_a_run_with_nothing_measured_yet_shows_no_spend_even_though_it_already_has_a_step(self) -> None:
        status = SliceStatus(
            sub_issue=SubIssueMother.blocked(IssueLabel.IN_PROGRESS, RunMother.implementing()), pull_request=None
        )

        rendered = FeatureStatusReport(statuses=(status,)).rendered()

        assert "$" not in rendered

    def test_a_run_that_spent_something_shows_its_cost(self) -> None:
        spend = HarnessSpendMother.of_the_judge_call()
        status = SliceStatus(
            sub_issue=SubIssueMother.blocked(IssueLabel.IN_PROGRESS, RunMother.judging_after_spending(spend)),
            pull_request=None,
        )

        rendered = FeatureStatusReport(statuses=(status,)).rendered()

        assert f"{spend.cost_usd:.2f}" in rendered

    def test_a_run_that_spent_no_retry_at_all_does_not_print_retries_as_a_zero(self) -> None:
        status = SliceStatus(
            sub_issue=SubIssueMother.blocked(IssueLabel.IN_PROGRESS, RunMother.implementing()), pull_request=None
        )

        rendered = FeatureStatusReport(statuses=(status,)).rendered()

        assert "retries" not in rendered

    def test_a_run_that_spent_retries_shows_how_many(self) -> None:
        run = RunMother.blocked_on_red_ci()
        status = SliceStatus(sub_issue=SubIssueMother.blocked(IssueLabel.BLOCKED_CI_RED, run), pull_request=None)

        rendered = FeatureStatusReport(statuses=(status,)).rendered()

        assert str(run.implement_retries) in rendered
        assert "retries" in rendered

    def test_a_slice_whose_branch_carries_a_pull_request_shows_its_number(self) -> None:
        status = SliceStatus(sub_issue=SubIssueMother.pending(), pull_request=47)

        rendered = FeatureStatusReport(statuses=(status,)).rendered()

        assert "47" in rendered

    def test_a_slice_with_no_open_pull_request_carries_no_number_at_all(self) -> None:
        status = SliceStatus(sub_issue=SubIssueMother.pending(), pull_request=None)

        rendered = FeatureStatusReport(statuses=(status,)).rendered()

        assert "#" not in rendered
