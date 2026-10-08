use crate::domain::parent::Parent;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FollowLine {
    repo: String,
    issue: u64,
    slice_id: String,
    step: String,
    status: String,
    parent: Parent,
    name: Option<String>,
}

impl FollowLine {
    pub fn new(
        repo: &str,
        issue: u64,
        slice_id: &str,
        step: &str,
        status: &str,
        parent: Parent,
        name: Option<&str>,
    ) -> Self {
        Self {
            repo: repo.to_string(),
            issue,
            slice_id: slice_id.to_string(),
            step: step.to_string(),
            status: status.to_string(),
            parent,
            name: name.map(str::to_string),
        }
    }

    pub fn repo(&self) -> &str {
        &self.repo
    }

    pub fn issue(&self) -> u64 {
        self.issue
    }

    pub fn slice_id(&self) -> &str {
        &self.slice_id
    }

    pub fn step(&self) -> &str {
        &self.step
    }

    pub fn status(&self) -> &str {
        &self.status
    }

    pub fn parent(&self) -> Parent {
        self.parent
    }

    pub fn name(&self) -> Option<&str> {
        self.name.as_deref()
    }
}
