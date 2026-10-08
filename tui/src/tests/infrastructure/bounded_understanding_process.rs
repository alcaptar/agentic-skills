mod integration {
    use std::time::{Duration, Instant};

    use crate::domain::errors::UnderstandingUnread;
    use crate::domain::understanding::Understanding;
    use crate::domain::understanding_source::UnderstandingSource;
    use crate::infrastructure::bounded_understanding_process::BoundedUnderstandingProcess;
    use crate::tests::application::watching::Watching;
    use crate::tests::infrastructure::endless_follow_process::SleepingChild;

    const GENEROUS: Duration = Duration::from_secs(10);

    struct Shell;

    impl Shell {
        fn running(script: &str, budget: Duration) -> BoundedUnderstandingProcess {
            BoundedUnderstandingProcess::new(vec!["sh".to_string(), "-c".to_string(), script.to_string()], budget)
        }
    }

    #[test]
    fn a_process_that_never_ends_is_killed_at_the_budget_and_the_call_returns_in_under_a_second() {
        let child = SleepingChild::announcing_in("bounded-understanding");
        let budget = Duration::from_millis(100);
        let mut process = BoundedUnderstandingProcess::new(child.argv(), budget);
        let started = Instant::now();

        let outcome = process.understanding_of(&Watching::key(504));

        assert!(started.elapsed() < Duration::from_secs(1), "{:?}", started.elapsed());
        assert_eq!(outcome, Err(UnderstandingUnread::TimedOut { budget }));
        assert!(!SleepingChild::is_alive(child.pid()));
    }

    #[test]
    fn exit_code_sixteen_is_no_understanding_published_and_not_a_failure() {
        let mut process = Shell::running("exit 16", GENEROUS);

        assert_eq!(
            process.understanding_of(&Watching::key(504)),
            Ok(Understanding::NotPublished)
        );
    }

    #[test]
    fn a_zero_exit_with_a_line_of_the_contract_is_the_published_understanding() {
        let mut process = Shell::running(r#"printf '%s\n' '{"version":1,"text":"hola"}'"#, GENEROUS);

        assert_eq!(
            process.understanding_of(&Watching::key(504)),
            Ok(Understanding::Published {
                text: "hola".to_string()
            })
        );
    }

    #[test]
    fn any_other_exit_code_is_a_failed_command_carrying_the_standard_error() {
        let mut process = Shell::running("echo 'gh is not authenticated' >&2; exit 1", GENEROUS);

        assert_eq!(
            process.understanding_of(&Watching::key(504)),
            Err(UnderstandingUnread::CommandFailed {
                reason: "gh is not authenticated".to_string()
            })
        );
    }

    #[test]
    fn asks_for_the_understanding_of_the_issue_of_the_slice_in_its_repo_as_json() {
        let mut process = Shell::running(r#"echo "$0 $@" >&2; exit 1"#, GENEROUS);

        let outcome = process.understanding_of(&Watching::key(504));

        assert_eq!(
            outcome,
            Err(UnderstandingUnread::CommandFailed {
                reason: "understanding 504 --repo alcaptar/agentic-skills --json".to_string()
            })
        );
    }

    #[test]
    fn a_program_that_does_not_exist_is_a_failed_command() {
        let mut process =
            BoundedUnderstandingProcess::new(vec!["slice-runner-that-does-not-exist".to_string()], GENEROUS);

        assert!(matches!(
            process.understanding_of(&Watching::key(504)),
            Err(UnderstandingUnread::CommandFailed { .. })
        ));
    }
}
