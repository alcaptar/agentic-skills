use std::collections::VecDeque;
use std::path::Path;
use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use crate::domain::clock::Clock;
use crate::domain::errors::{FollowLineRejected, IssuesUnread};
use crate::domain::follow_entry::FollowEntry;
use crate::domain::follow_source::FollowSource;
use crate::domain::issue_source::IssueSource;
use crate::domain::liveness::Liveness;
use crate::domain::open_issue::OpenIssue;
use crate::domain::process_probe::ProcessProbe;
use crate::domain::session_transcripts::SessionTranscripts;
use crate::domain::workspace_id::WorkspaceId;
use crate::domain::workspace_ids::WorkspaceIds;
use crate::tests::mothers::workspace_mother::WorkspaceMother;

pub type Delivery = Result<FollowEntry, FollowLineRejected>;

pub struct ScriptedFollowSource {
    batches: VecDeque<Vec<Delivery>>,
}

impl ScriptedFollowSource {
    pub fn delivering(batches: Vec<Vec<Delivery>>) -> Self {
        Self {
            batches: batches.into(),
        }
    }
}

impl FollowSource for ScriptedFollowSource {
    fn pending(&mut self) -> Vec<Delivery> {
        self.batches.pop_front().unwrap_or_default()
    }
}

pub struct FixedWorkspaceIds {
    id: WorkspaceId,
}

impl FixedWorkspaceIds {
    pub fn always(text: &str) -> Self {
        Self {
            id: WorkspaceId::parse(text).unwrap(),
        }
    }
}

impl WorkspaceIds for FixedWorkspaceIds {
    fn next(&mut self) -> WorkspaceId {
        self.id.clone()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Call {
    RepoView,
    IssueList { repo: String, limit: usize },
    IssueView { repo: String, number: u64 },
}

pub type Calls = Arc<Mutex<Vec<Call>>>;

pub struct ScriptedIssueSource {
    repos: VecDeque<Result<String, IssuesUnread>>,
    lists: VecDeque<Result<Vec<OpenIssue>, IssuesUnread>>,
    bodies: VecDeque<Result<String, IssuesUnread>>,
    calls: Calls,
}

impl ScriptedIssueSource {
    pub fn answering(
        repos: Vec<Result<String, IssuesUnread>>,
        lists: Vec<Result<Vec<OpenIssue>, IssuesUnread>>,
    ) -> (Self, Calls) {
        let calls = Calls::default();

        (
            Self {
                repos: repos.into(),
                lists: lists.into(),
                bodies: VecDeque::new(),
                calls: Arc::clone(&calls),
            },
            calls,
        )
    }

    pub fn with_bodies(mut self, bodies: Vec<Result<String, IssuesUnread>>) -> Self {
        self.bodies = bodies.into();

        self
    }

    fn unscripted(what: &str) -> IssuesUnread {
        IssuesUnread::CommandFailed {
            reason: format!("nobody scripted an answer for {what}"),
        }
    }
}

impl IssueSource for ScriptedIssueSource {
    fn repo_of_directory(&mut self) -> Result<String, IssuesUnread> {
        self.calls.lock().unwrap().push(Call::RepoView);

        self.repos
            .pop_front()
            .unwrap_or_else(|| Err(Self::unscripted("repo view")))
    }

    fn latest_open(&mut self, repo: &str, limit: usize) -> Result<Vec<OpenIssue>, IssuesUnread> {
        self.calls.lock().unwrap().push(Call::IssueList {
            repo: repo.to_string(),
            limit,
        });

        self.lists
            .pop_front()
            .unwrap_or_else(|| Err(Self::unscripted("issue list")))
    }

    fn body_of(&mut self, repo: &str, number: u64) -> Result<String, IssuesUnread> {
        self.calls.lock().unwrap().push(Call::IssueView {
            repo: repo.to_string(),
            number,
        });

        self.bodies
            .pop_front()
            .unwrap_or_else(|| Err(Self::unscripted("issue view")))
    }
}

pub struct ScriptedTranscripts {
    existing: bool,
}

impl ScriptedTranscripts {
    pub fn present() -> Self {
        Self { existing: true }
    }

    pub fn absent() -> Self {
        Self { existing: false }
    }
}

impl SessionTranscripts for ScriptedTranscripts {
    fn exists(&self, _directory: &Path, _id: &WorkspaceId) -> bool {
        self.existing
    }
}

#[derive(Clone)]
pub struct SteppedClock {
    start: Instant,
    elapsed: Arc<Mutex<Duration>>,
}

impl SteppedClock {
    pub fn standing_still() -> Self {
        Self {
            start: Instant::now(),
            elapsed: Arc::default(),
        }
    }

    pub fn advance(&self, by: Duration) {
        *self.elapsed.lock().unwrap() += by;
    }
}

impl Clock for SteppedClock {
    fn now(&self) -> Instant {
        self.start + *self.elapsed.lock().unwrap()
    }
}

pub struct GatedIssueSource {
    gate: Receiver<()>,
}

impl GatedIssueSource {
    pub fn closed() -> (Self, Sender<()>) {
        let (release, gate) = mpsc::channel();

        (Self { gate }, release)
    }
}

impl IssueSource for GatedIssueSource {
    fn repo_of_directory(&mut self) -> Result<String, IssuesUnread> {
        Ok(WorkspaceMother::REPO.to_string())
    }

    fn latest_open(&mut self, _repo: &str, _limit: usize) -> Result<Vec<OpenIssue>, IssuesUnread> {
        self.gate.recv().ok();

        Ok(vec![WorkspaceMother::parent_of_this_workspace(9)])
    }

    fn body_of(&mut self, _repo: &str, _number: u64) -> Result<String, IssuesUnread> {
        Err(IssuesUnread::CommandFailed {
            reason: "nobody scripted an answer for issue view".to_string(),
        })
    }
}

pub struct FixedProbe {
    alive: Vec<u32>,
    everyone_alive: bool,
}

impl FixedProbe {
    pub fn everyone_alive() -> Self {
        Self {
            alive: Vec::new(),
            everyone_alive: true,
        }
    }

    pub fn alive_only(alive: &[u32]) -> Self {
        Self {
            alive: alive.to_vec(),
            everyone_alive: false,
        }
    }
}

impl ProcessProbe for FixedProbe {
    fn liveness_of(&self, pid: u32) -> Liveness {
        if self.everyone_alive || self.alive.contains(&pid) {
            return Liveness::Alive;
        }

        Liveness::Gone
    }
}

pub struct UnaskedProbe;

impl ProcessProbe for UnaskedProbe {
    fn liveness_of(&self, pid: u32) -> Liveness {
        panic!("the probe was asked about {pid}")
    }
}
