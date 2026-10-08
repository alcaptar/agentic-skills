use std::cell::RefCell;
use std::collections::VecDeque;
use std::rc::Rc;

use crate::domain::errors::{FollowLineRejected, UnderstandingUnread};
use crate::domain::follow_line::FollowLine;
use crate::domain::follow_source::FollowSource;
use crate::domain::slice_key::SliceKey;
use crate::domain::understanding::Understanding;
use crate::domain::understanding_source::UnderstandingSource;
use crate::domain::workspace_id::WorkspaceId;
use crate::domain::workspace_ids::WorkspaceIds;

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

pub type Asked = Rc<RefCell<Vec<SliceKey>>>;

pub struct ScriptedUnderstandingSource {
    answer: Result<Understanding, UnderstandingUnread>,
    asked: Asked,
}

impl ScriptedUnderstandingSource {
    pub fn answering(answer: Result<Understanding, UnderstandingUnread>) -> (Self, Asked) {
        let asked = Asked::default();

        (
            Self {
                answer,
                asked: Rc::clone(&asked),
            },
            asked,
        )
    }
}

impl UnderstandingSource for ScriptedUnderstandingSource {
    fn understanding_of(&mut self, key: &SliceKey) -> Result<Understanding, UnderstandingUnread> {
        self.asked.borrow_mut().push(key.clone());

        self.answer.clone()
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
