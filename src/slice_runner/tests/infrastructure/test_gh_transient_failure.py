from __future__ import annotations

from slice_runner.infrastructure.gh_transient_failure import GhTransientFailure


class TestGhTransientFailure:
    def test_a_connection_reset_is_read_as_transient(self) -> None:
        assert GhTransientFailure.of('Post "https://api.github.com/graphql": read: connection reset by peer')

    def test_a_secondary_rate_limit_is_read_as_transient(self) -> None:
        assert GhTransientFailure.of(
            "HTTP 403: You have exceeded a secondary rate limit and have been temporarily blocked"
        )

    def test_a_bad_gateway_is_read_as_transient(self) -> None:
        assert GhTransientFailure.of("HTTP 502: Bad Gateway")

    def test_matching_ignores_case(self) -> None:
        assert GhTransientFailure.of("Connection Reset by peer")

    def test_a_missing_issue_is_not_read_as_transient(self) -> None:
        assert not GhTransientFailure.of("GraphQL: Could not resolve to an Issue with the number of 999999.")

    def test_a_missing_permission_is_not_read_as_transient(self) -> None:
        assert not GhTransientFailure.of("HTTP 403: Resource not accessible by integration")

    def test_a_shorthand_rate_limited_fixture_is_not_mistaken_for_the_real_message(self) -> None:
        assert not GhTransientFailure.of("rate limited")
