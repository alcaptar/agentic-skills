use std::path::PathBuf;
use std::process::Command;
use std::time::{Duration, Instant};

pub struct Waiting;

impl Waiting {
    pub fn until<T>(mut probe: impl FnMut() -> Option<T>) -> T {
        let deadline = Instant::now() + Duration::from_secs(10);
        loop {
            if let Some(found) = probe() {
                return found;
            }
            assert!(Instant::now() < deadline, "nothing happened within the deadline");
            std::thread::sleep(Duration::from_millis(20));
        }
    }
}

pub struct SleepingChild {
    pid_file: PathBuf,
}

impl SleepingChild {
    pub const SCRIPT: &'static str = "echo $$ > \"$0\"; exec sleep 60";

    pub fn announcing_in(name: &str) -> Self {
        let pid_file = std::env::temp_dir().join(format!("slice-runner-tui-{}-{name}", std::process::id()));
        std::fs::remove_file(&pid_file).ok();

        Self { pid_file }
    }

    pub fn argv(&self) -> Vec<String> {
        vec![
            "sh".to_string(),
            "-c".to_string(),
            Self::SCRIPT.to_string(),
            self.pid_file.display().to_string(),
        ]
    }

    pub fn pid(&self) -> u32 {
        Waiting::until(|| {
            std::fs::read_to_string(&self.pid_file)
                .ok()
                .filter(|text| text.ends_with('\n'))
        })
        .trim()
        .parse()
        .unwrap()
    }

    pub fn is_alive(pid: u32) -> bool {
        Command::new("kill")
            .arg("-0")
            .arg(pid.to_string())
            .output()
            .unwrap()
            .status
            .success()
    }
}

impl Drop for SleepingChild {
    fn drop(&mut self) {
        std::fs::remove_file(&self.pid_file).ok();
    }
}

mod integration {
    use std::panic::{AssertUnwindSafe, catch_unwind};

    use crate::domain::errors::FollowLineRejected;
    use crate::domain::follow_source::FollowSource;
    use crate::infrastructure::endless_follow_process::EndlessFollowProcess;
    use crate::tests::infrastructure::endless_follow_process::{SleepingChild, Waiting};

    #[test]
    fn the_process_is_gone_once_the_adapter_is_dropped() {
        let child = SleepingChild::announcing_in("normal-exit");
        let process = EndlessFollowProcess::spawn(&child.argv()).unwrap();
        let pid = child.pid();
        assert!(SleepingChild::is_alive(pid));

        drop(process);

        assert!(!SleepingChild::is_alive(pid));
    }

    #[test]
    fn the_process_is_gone_when_the_interface_falls_by_a_panic() {
        let child = SleepingChild::announcing_in("panic");
        let mut seen_pid = 0;

        let outcome = catch_unwind(AssertUnwindSafe(|| {
            let _process = EndlessFollowProcess::spawn(&child.argv()).unwrap();
            seen_pid = child.pid();
            panic!("the interface fell");
        }));

        assert!(outcome.is_err());
        assert_ne!(seen_pid, 0);
        assert!(!SleepingChild::is_alive(seen_pid));
    }

    #[test]
    fn delivers_each_line_parsed_and_reports_when_follow_ends() {
        let argv = [
            "sh",
            "-c",
            r#"printf '%s\n' '{"repo":"a/b","issue":1,"slice_id":"slice-01","step":"implement","status":"advancing"}' 'garbage'"#,
        ];
        let mut process = EndlessFollowProcess::spawn(&argv).unwrap();
        let mut delivered = Vec::new();

        Waiting::until(|| {
            delivered.extend(process.pending());
            (delivered.len() >= 3).then_some(())
        });

        assert_eq!(delivered[0].as_ref().unwrap().slice_id(), "slice-01");
        assert_eq!(
            delivered[1],
            Err(FollowLineRejected::NotJson {
                line: "garbage".to_string()
            })
        );
        assert_eq!(delivered[2], Err(FollowLineRejected::FollowEnded));
    }

    #[test]
    fn a_program_that_does_not_exist_is_a_typed_rejection() {
        let rejected = EndlessFollowProcess::spawn(&["slice-runner-that-does-not-exist"]).err();

        assert!(
            matches!(rejected, Some(FollowLineRejected::FollowNotLaunched { .. })),
            "{rejected:?}"
        );
    }
}
