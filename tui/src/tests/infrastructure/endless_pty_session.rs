use std::path::PathBuf;

use crate::domain::pane_size::PaneSize;
use crate::domain::session_launch::SessionLaunch;
use crate::infrastructure::endless_pty_session::EndlessPtySession;

pub struct Launches;

impl Launches {
    pub fn of(argv: Vec<String>) -> SessionLaunch {
        SessionLaunch::new(argv, std::env::temp_dir(), Vec::new())
    }

    pub fn shell(script: &str) -> SessionLaunch {
        Self::of(vec!["sh".to_string(), "-c".to_string(), script.to_string()])
    }

    pub fn shell_in(script: &str, directory: PathBuf, environment: Vec<(String, String)>) -> SessionLaunch {
        SessionLaunch::new(
            vec!["sh".to_string(), "-c".to_string(), script.to_string()],
            directory,
            environment,
        )
    }

    pub fn size() -> PaneSize {
        PaneSize::new(24, 80)
    }

    pub fn text_of(session: &EndlessPtySession) -> String {
        session.with_screen(vt100::Screen::contents)
    }
}

mod integration {
    use std::panic::{AssertUnwindSafe, catch_unwind};

    use crate::domain::pane_size::PaneSize;
    use crate::infrastructure::endless_pty_session::EndlessPtySession;
    use crate::tests::infrastructure::endless_follow_process::{SleepingChild, Waiting};
    use crate::tests::infrastructure::endless_pty_session::Launches;

    #[test]
    fn the_process_is_gone_once_the_adapter_is_dropped() {
        let child = SleepingChild::announcing_in("pty-normal-exit");
        let session = EndlessPtySession::spawn(&Launches::of(child.argv()), Launches::size()).unwrap();
        let pid = child.pid();
        assert!(SleepingChild::is_alive(pid));

        drop(session);

        assert!(!SleepingChild::is_alive(pid));
    }

    #[test]
    fn the_process_is_gone_when_the_interface_falls_by_a_panic() {
        let child = SleepingChild::announcing_in("pty-panic");
        let mut seen_pid = 0;

        let outcome = catch_unwind(AssertUnwindSafe(|| {
            let _session = EndlessPtySession::spawn(&Launches::of(child.argv()), Launches::size()).unwrap();
            seen_pid = child.pid();
            panic!("the interface fell");
        }));

        assert!(outcome.is_err());
        assert_ne!(seen_pid, 0);
        assert!(!SleepingChild::is_alive(seen_pid));
    }

    #[test]
    fn the_child_gets_exactly_the_rows_and_columns_of_the_pane_and_the_new_ones_after_a_resize() {
        let script = "stty size; read line; stty size; read line";
        let mut session = EndlessPtySession::spawn(&Launches::shell(script), PaneSize::new(24, 40)).unwrap();
        Waiting::until(|| Launches::text_of(&session).contains("24 40").then_some(()));

        session.resize(PaneSize::new(10, 30));
        session.write(b"\n");

        Waiting::until(|| Launches::text_of(&session).contains("10 30").then_some(()));
    }

    #[test]
    fn the_child_runs_in_the_given_directory_with_the_given_variables() {
        let directory = std::fs::canonicalize(std::env::temp_dir()).unwrap();
        let launch = Launches::shell_in(
            "echo \"workspace=$SLICE_RUNNER_WORKSPACE\"; pwd; sleep 60",
            directory.clone(),
            vec![("SLICE_RUNNER_WORKSPACE".to_string(), "abc".to_string())],
        );
        let session = EndlessPtySession::spawn(&launch, Launches::size()).unwrap();

        let text = Waiting::until(|| Some(Launches::text_of(&session)).filter(|text| text.contains("workspace=abc")));

        assert!(text.contains(&directory.display().to_string()), "{text}");
    }

    #[test]
    fn it_reports_the_end_of_the_child_and_keeps_the_last_screen() {
        let mut session = EndlessPtySession::spawn(&Launches::shell("echo bye"), Launches::size()).unwrap();

        Waiting::until(|| session.has_ended().then_some(()));

        Waiting::until(|| Launches::text_of(&session).contains("bye").then_some(()));
    }

    #[test]
    fn a_program_that_does_not_exist_is_a_typed_rejection() {
        let rejected = EndlessPtySession::spawn(
            &Launches::of(vec!["slice-runner-that-does-not-exist".to_string()]),
            Launches::size(),
        )
        .err();

        assert!(rejected.is_some());
    }
}
