use crate::domain::follow_line::FollowLine;
use crate::domain::parent::Parent;

pub struct FollowLineMother;

impl FollowLineMother {
    pub const REPO: &'static str = "alcaptar/agentic-skills";
    pub const NAME: &'static str = "follow-speaks-json";

    pub fn child_of(parent: u64, issue: u64) -> FollowLine {
        FollowLine::new(
            Self::REPO,
            issue,
            "slice-01",
            "run-controls",
            "advancing",
            Parent::Issue(parent),
            Some(Self::NAME),
        )
    }

    pub fn child_of_in_repo(repo: &str, parent: u64, issue: u64) -> FollowLine {
        FollowLine::new(
            repo,
            issue,
            "slice-01",
            "run-controls",
            "advancing",
            Parent::Issue(parent),
            Some(Self::NAME),
        )
    }

    pub fn orphan(issue: u64) -> FollowLine {
        FollowLine::new(
            Self::REPO,
            issue,
            "slice-02",
            "implement",
            "advancing",
            Parent::Absent,
            None,
        )
    }

    pub fn closed(earlier: &FollowLine) -> FollowLine {
        FollowLine::new(
            earlier.repo(),
            earlier.issue(),
            earlier.slice_id(),
            "await-merge",
            "closed",
            earlier.parent(),
            earlier.name(),
        )
    }

    pub fn closed_without_parent_or_name(earlier: &FollowLine) -> FollowLine {
        FollowLine::new(
            earlier.repo(),
            earlier.issue(),
            earlier.slice_id(),
            "await-merge",
            "closed",
            Parent::Absent,
            None,
        )
    }

    pub fn moved_to(earlier: &FollowLine, step: &str) -> FollowLine {
        FollowLine::new(
            earlier.repo(),
            earlier.issue(),
            earlier.slice_id(),
            step,
            "advancing",
            earlier.parent(),
            earlier.name(),
        )
    }
}
