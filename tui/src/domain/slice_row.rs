use crate::domain::follow_line::FollowLine;
use crate::domain::parent::Parent;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SliceRow {
    line: FollowLine,
    parent: Parent,
    name: Option<String>,
}

impl SliceRow {
    pub fn first(line: FollowLine) -> Self {
        Self {
            parent: line.parent(),
            name: line.name().map(str::to_string),
            line,
        }
    }

    pub fn with_line(&self, line: FollowLine) -> Self {
        Self {
            parent: line.parent().or_known(self.parent),
            name: line.name().map(str::to_string).or_else(|| self.name.clone()),
            line,
        }
    }

    pub fn is_the_slice_of(&self, line: &FollowLine) -> bool {
        self.line.repo() == line.repo() && self.line.issue() == line.issue()
    }

    pub fn repo(&self) -> &str {
        self.line.repo()
    }

    pub fn slice_id(&self) -> &str {
        self.line.slice_id()
    }

    pub fn step(&self) -> &str {
        self.line.step()
    }

    pub fn status(&self) -> &str {
        self.line.status()
    }

    pub fn parent(&self) -> Parent {
        self.parent
    }

    pub fn name(&self) -> Option<&str> {
        self.name.as_deref()
    }

    pub fn label(&self) -> &str {
        self.name().unwrap_or_else(|| self.slice_id())
    }
}
