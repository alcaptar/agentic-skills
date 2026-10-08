use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{Receiver, channel};
use std::thread;

use crate::domain::errors::FollowLineRejected;
use crate::domain::follow_line::FollowLine;
use crate::domain::follow_source::FollowSource;
use crate::infrastructure::follow_line_payload::FollowLinePayload;

pub struct EndlessFollowProcess {
    child: Child,
    deliveries: Receiver<Result<FollowLine, FollowLineRejected>>,
}

impl EndlessFollowProcess {
    pub fn spawn<S: AsRef<str>>(argv: &[S]) -> Result<Self, FollowLineRejected> {
        let (program, arguments) = argv.split_first().ok_or_else(|| Self::not_launched("empty command"))?;
        let mut child = Command::new(program.as_ref())
            .args(arguments.iter().map(AsRef::as_ref))
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|error| Self::not_launched(&error.to_string()))?;
        let Some(stdout) = child.stdout.take() else {
            child.kill().ok();
            child.wait().ok();
            return Err(Self::not_launched("no standard output"));
        };
        let (sender, deliveries) = channel();
        thread::spawn(move || {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                if sender.send(FollowLinePayload::parsed(&line)).is_err() {
                    return;
                }
            }
            sender.send(Err(FollowLineRejected::FollowEnded)).ok();
        });

        Ok(Self { child, deliveries })
    }

    fn not_launched(reason: &str) -> FollowLineRejected {
        FollowLineRejected::FollowNotLaunched {
            reason: reason.to_string(),
        }
    }
}

impl FollowSource for EndlessFollowProcess {
    fn pending(&mut self) -> Vec<Result<FollowLine, FollowLineRejected>> {
        self.deliveries.try_iter().collect()
    }
}

impl Drop for EndlessFollowProcess {
    fn drop(&mut self) {
        self.child.kill().ok();
        self.child.wait().ok();
    }
}
