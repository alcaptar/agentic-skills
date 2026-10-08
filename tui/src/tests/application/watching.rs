use crate::application::queries::watch_slices::{WatchSlices, WatchedBoard};
use crate::domain::errors::FollowLineRejected;
use crate::domain::follow_line::FollowLine;
use crate::domain::slice_board::SliceBoard;
use crate::domain::slice_key::SliceKey;
use crate::tests::doubles::{Delivery, ScriptedFollowSource};
use crate::tests::mothers::follow_line_mother::FollowLineMother;

pub struct Watching;

impl Watching {
    pub fn one_tick(lines: Vec<Delivery>) -> WatchedBoard {
        let mut watch = WatchSlices::new(ScriptedFollowSource::delivering(vec![lines]));

        watch.execute(SliceBoard::empty())
    }

    pub fn lines(lines: Vec<FollowLine>) -> Vec<Delivery> {
        lines.into_iter().map(Ok).collect()
    }

    pub fn wrong_issue() -> FollowLineRejected {
        FollowLineRejected::WrongValue {
            key: "issue".to_string(),
            reason: "expected a number".to_string(),
        }
    }

    pub fn key(issue: u64) -> SliceKey {
        SliceKey::new(FollowLineMother::REPO, issue)
    }

    pub fn three_slices_in_two_groups() -> WatchedBoard {
        Self::one_tick(Self::lines(vec![
            FollowLineMother::orphan(170),
            FollowLineMother::child_of(141, 160),
            FollowLineMother::child_of(140, 150),
        ]))
    }
}
