use std::collections::VecDeque;

use crate::domain::errors::FollowLineRejected;
use crate::domain::follow_line::FollowLine;
use crate::domain::follow_source::FollowSource;

pub type Delivery = Result<FollowLine, FollowLineRejected>;

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
