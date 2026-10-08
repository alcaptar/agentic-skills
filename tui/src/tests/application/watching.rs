use crate::application::queries::watch_slices::{WatchSlices, WatchedBoard};
use crate::domain::errors::FollowLineRejected;
use crate::domain::follow_line::FollowLine;
use crate::domain::slice_board::SliceBoard;
use crate::tests::doubles::{Delivery, ScriptedFollowSource};

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
}
