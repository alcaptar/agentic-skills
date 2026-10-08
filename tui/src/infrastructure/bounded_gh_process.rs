use std::io::Read;
use std::process::{Child, Command, ExitStatus, Stdio};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

use crate::domain::errors::IssuesUnread;
use crate::domain::issue_source::IssueSource;
use crate::domain::open_issue::OpenIssue;
use crate::infrastructure::open_issues_payload::OpenIssuesPayload;
use crate::infrastructure::repo_view_payload::RepoViewPayload;

pub struct BoundedGhProcess {
    program: Vec<String>,
    budget: Duration,
}

impl BoundedGhProcess {
    const POLL: Duration = Duration::from_millis(10);

    pub fn new(program: Vec<String>, budget: Duration) -> Self {
        Self { program, budget }
    }

    fn launched(&self, arguments: &[&str]) -> Result<Child, IssuesUnread> {
        let (program, prefix) = self
            .program
            .split_first()
            .ok_or_else(|| Self::failed("empty command"))?;

        Command::new(program)
            .args(prefix)
            .args(arguments)
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

    fn answer_of(&self, arguments: &[&str]) -> Result<String, IssuesUnread> {
        let mut child = self.launched(arguments)?;
        let stdout = Self::drained(child.stdout.take());
        let stderr = Self::drained(child.stderr.take());
        let deadline = Instant::now() + self.budget;
        loop {
            match child.try_wait() {
                Ok(Some(status)) => {
                    return Self::interpreted(
                        status,
                        stdout.join().unwrap_or_default(),
                        &stderr.join().unwrap_or_default(),
                    );
                }
                Ok(None) if Instant::now() < deadline => thread::sleep(Self::POLL),
                Ok(None) => {
                    Self::abandoned(&mut child);
                    return Err(IssuesUnread::TimedOut { budget: self.budget });
                }
                Err(error) => {
                    Self::abandoned(&mut child);
                    return Err(Self::failed(&error.to_string()));
                }
            }
        }
    }

    fn interpreted(status: ExitStatus, stdout: String, stderr: &str) -> Result<String, IssuesUnread> {
        match status.code() {
            Some(0) => Ok(stdout),
            Some(code) if stderr.trim().is_empty() => Err(Self::failed(&format!("exited with code {code}"))),
            Some(_) => Err(Self::failed(stderr.trim())),
            None => Err(Self::failed("terminated by a signal")),
        }
    }

    fn failed(reason: &str) -> IssuesUnread {
        IssuesUnread::CommandFailed {
            reason: reason.to_string(),
        }
    }
}

impl IssueSource for BoundedGhProcess {
    fn repo_of_directory(&mut self) -> Result<String, IssuesUnread> {
        let answer = self.answer_of(&["repo", "view", "--json", RepoViewPayload::KEY])?;

        RepoViewPayload::parsed(&answer)
    }

    fn latest_open(&mut self, repo: &str, limit: usize) -> Result<Vec<OpenIssue>, IssuesUnread> {
        let answer = self.answer_of(&[
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            &limit.to_string(),
            "--json",
            &OpenIssuesPayload::KEYS.join(","),
        ])?;

        OpenIssuesPayload::parsed(&answer)
    }
}
