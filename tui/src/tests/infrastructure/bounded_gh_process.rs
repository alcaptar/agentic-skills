mod integration {
    use std::time::{Duration, Instant};

    use crate::domain::errors::IssuesUnread;
    use crate::domain::issue_source::IssueSource;
    use crate::domain::open_issue::OpenIssue;
    use crate::infrastructure::bounded_gh_process::BoundedGhProcess;
    use crate::tests::infrastructure::endless_follow_process::SleepingChild;

    const GENEROUS: Duration = Duration::from_secs(10);

    struct Shell;

    impl Shell {
        fn running(script: &str, budget: Duration) -> BoundedGhProcess {
            BoundedGhProcess::new(vec!["sh".to_string(), "-c".to_string(), script.to_string()], budget)
        }
    }

    #[test]
    fn a_repo_view_that_never_ends_is_killed_at_the_budget_and_the_call_returns_in_under_a_second() {
        let child = SleepingChild::announcing_in("bounded-gh-repo-view");
        let budget = Duration::from_millis(100);
        let mut process = BoundedGhProcess::new(child.argv(), budget);
        let started = Instant::now();

        let outcome = process.repo_of_directory();

        assert!(started.elapsed() < Duration::from_secs(1), "{:?}", started.elapsed());
        assert_eq!(outcome, Err(IssuesUnread::TimedOut { budget }));
        assert!(!SleepingChild::is_alive(child.pid()));
    }

    #[test]
    fn an_issue_list_that_never_ends_is_killed_at_the_budget() {
        let child = SleepingChild::announcing_in("bounded-gh-issue-list");
        let budget = Duration::from_millis(100);
        let mut process = BoundedGhProcess::new(child.argv(), budget);

        let outcome = process.latest_open("alcaptar/agentic-skills", 20);

        assert_eq!(outcome, Err(IssuesUnread::TimedOut { budget }));
        assert!(!SleepingChild::is_alive(child.pid()));
    }

    #[test]
    fn asks_gh_for_the_name_with_owner_of_the_repo_of_the_directory() {
        let mut process = Shell::running(r#"echo "$0 $@" >&2; exit 1"#, GENEROUS);

        assert_eq!(
            process.repo_of_directory(),
            Err(IssuesUnread::CommandFailed {
                reason: "repo view --json nameWithOwner".to_string()
            })
        );
    }

    #[test]
    fn asks_gh_for_the_open_issues_of_the_repo_with_the_limit_and_the_fields_of_the_contract() {
        let mut process = Shell::running(r#"echo "$0 $@" >&2; exit 1"#, GENEROUS);

        assert_eq!(
            process.latest_open("alcaptar/agentic-skills", 20),
            Err(IssuesUnread::CommandFailed {
                reason: "issue list --repo alcaptar/agentic-skills --state open --limit 20 --json number,body"
                    .to_string()
            })
        );
    }

    #[test]
    fn a_zero_exit_with_the_literal_answer_of_gh_is_the_repo() {
        let mut process = Shell::running(
            r#"printf '%s\n' '{"nameWithOwner":"alcaptar/agentic-skills"}'"#,
            GENEROUS,
        );

        assert_eq!(process.repo_of_directory(), Ok("alcaptar/agentic-skills".to_string()));
    }

    #[test]
    fn a_zero_exit_with_the_literal_answer_of_gh_is_the_list_of_issues() {
        let mut process = Shell::running(r#"printf '%s\n' '[{"body":"hola","number":9}]'"#, GENEROUS);

        assert_eq!(
            process.latest_open("alcaptar/agentic-skills", 20),
            Ok(vec![OpenIssue::new(9, "hola")])
        );
    }

    #[test]
    fn a_non_zero_exit_is_a_failed_command_carrying_the_standard_error() {
        let mut process = Shell::running("echo 'gh is not authenticated' >&2; exit 4", GENEROUS);

        assert_eq!(
            process.repo_of_directory(),
            Err(IssuesUnread::CommandFailed {
                reason: "gh is not authenticated".to_string()
            })
        );
    }

    #[test]
    fn a_non_zero_exit_without_standard_error_names_the_code() {
        let mut process = Shell::running("exit 4", GENEROUS);

        assert_eq!(
            process.repo_of_directory(),
            Err(IssuesUnread::CommandFailed {
                reason: "exited with code 4".to_string()
            })
        );
    }

    #[test]
    fn a_program_that_does_not_exist_is_a_failed_command() {
        let mut process = BoundedGhProcess::new(vec!["gh-that-does-not-exist".to_string()], GENEROUS);

        assert!(matches!(
            process.repo_of_directory(),
            Err(IssuesUnread::CommandFailed { .. })
        ));
    }
}
