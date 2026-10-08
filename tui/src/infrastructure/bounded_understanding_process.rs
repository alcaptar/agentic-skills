use std::io::Read;
use std::process::{Child, Command, ExitStatus, Stdio};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

use crate::domain::errors::UnderstandingUnread;
use crate::domain::slice_key::SliceKey;
use crate::domain::understanding::Understanding;
use crate::domain::understanding_source::UnderstandingSource;
use crate::infrastructure::understanding_line_payload::UnderstandingLinePayload;

pub struct BoundedUnderstandingProcess {
    program: Vec<String>,
    budget: Duration,
}

impl BoundedUnderstandingProcess {
    const NO_UNDERSTANDING_EXIT_CODE: i32 = 16;
    const POLL: Duration = Duration::from_millis(10);

    pub fn new(program: Vec<String>, budget: Duration) -> Self {
        Self { program, budget }
    }

    fn launched(&self, key: &SliceKey) -> Result<Child, UnderstandingUnread> {
        let (program, arguments) = self
            .program
            .split_first()
            .ok_or_else(|| Self::failed("empty command"))?;

        Command::new(program)
            .args(arguments)
            .arg("understanding")
            .arg(key.issue().to_string())
            .args(["--repo", key.repo(), "--json"])
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|error| Self::failed(&error.to_string()))
    }

    fn drained<R: Read + Send + 'static>(stream: Option<R>) -> JoinHandle<String> {
        thread::spawn(move || {
            let mut bytes = Vec::new();
            if let Some(mut stream) = stream {
                stream.read_to_end(&mut bytes).ok();
            }

            String::from_utf8_lossy(&bytes).into_owned()
        })
    }

    fn abandoned(child: &mut Child) {
        child.kill().ok();
        child.wait().ok();
    }

    fn interpreted(status: ExitStatus, stdout: &str, stderr: &str) -> Result<Understanding, UnderstandingUnread> {
        match status.code() {
            Some(0) => UnderstandingLinePayload::parsed(stdout),
            Some(Self::NO_UNDERSTANDING_EXIT_CODE) => Ok(Understanding::NotPublished),
            Some(code) if stderr.trim().is_empty() => Err(Self::failed(&format!("exited with code {code}"))),
            Some(_) => Err(Self::failed(stderr.trim())),
            None => Err(Self::failed("terminated by a signal")),
        }
    }

    fn failed(reason: &str) -> UnderstandingUnread {
        UnderstandingUnread::CommandFailed {
            reason: reason.to_string(),
        }
    }
}

impl UnderstandingSource for BoundedUnderstandingProcess {
    fn understanding_of(&mut self, key: &SliceKey) -> Result<Understanding, UnderstandingUnread> {
        let mut child = self.launched(key)?;
        let stdout = Self::drained(child.stdout.take());
        let stderr = Self::drained(child.stderr.take());
        let deadline = Instant::now() + self.budget;
        loop {
            match child.try_wait() {
                Ok(Some(status)) => {
                    return Self::interpreted(
                        status,
                        &stdout.join().unwrap_or_default(),
                        &stderr.join().unwrap_or_default(),
                    );
                }
                Ok(None) if Instant::now() < deadline => thread::sleep(Self::POLL),
                Ok(None) => {
                    Self::abandoned(&mut child);
                    return Err(UnderstandingUnread::TimedOut { budget: self.budget });
                }
                Err(error) => {
                    Self::abandoned(&mut child);
                    return Err(Self::failed(&error.to_string()));
                }
            }
        }
    }
}
