use serde_json::{Map, Value};

use crate::domain::errors::FollowLineRejected;
use crate::domain::follow_line::FollowLine;
use crate::domain::parent::Parent;

pub struct FollowLinePayload {
    fields: Map<String, Value>,
}

impl FollowLinePayload {
    pub const REQUIRED_KEYS: [&'static str; 5] = ["repo", "issue", "slice_id", "step", "status"];

    pub fn parsed(raw: &str) -> Result<FollowLine, FollowLineRejected> {
        match serde_json::from_str::<Value>(raw) {
            Ok(Value::Object(fields)) => Self { fields }.to_domain(),
            Ok(_) | Err(_) => Err(FollowLineRejected::NotJson { line: raw.to_string() }),
        }
    }

    fn to_domain(&self) -> Result<FollowLine, FollowLineRejected> {
        if let Some(key) = Self::REQUIRED_KEYS
            .into_iter()
            .find(|key| !self.fields.contains_key(*key))
        {
            return Err(Self::wrong(key, "required key is missing"));
        }
        let parent = match self.optional_number("parent")? {
            Some(issue) => Parent::Issue(issue),
            None => Parent::Absent,
        };

        Ok(FollowLine::new(
            self.required_text("repo")?,
            self.required_number("issue")?,
            self.required_text("slice_id")?,
            self.required_text("step")?,
            self.required_text("status")?,
            parent,
            self.optional_text("name")?,
        ))
    }

    fn required_text(&self, key: &str) -> Result<&str, FollowLineRejected> {
        self.optional_text(key)?
            .ok_or_else(|| Self::wrong(key, "required key is missing"))
    }

    fn optional_text(&self, key: &str) -> Result<Option<&str>, FollowLineRejected> {
        match self.fields.get(key) {
            None => Ok(None),
            Some(value) => value
                .as_str()
                .map(Some)
                .ok_or_else(|| Self::wrong(key, "expected a string")),
        }
    }

    fn required_number(&self, key: &str) -> Result<u64, FollowLineRejected> {
        self.optional_number(key)?
            .ok_or_else(|| Self::wrong(key, "required key is missing"))
    }

    fn optional_number(&self, key: &str) -> Result<Option<u64>, FollowLineRejected> {
        match self.fields.get(key) {
            None => Ok(None),
            Some(value) => value
                .as_u64()
                .map(Some)
                .ok_or_else(|| Self::wrong(key, "expected a whole number")),
        }
    }

    fn wrong(key: &str, reason: &str) -> FollowLineRejected {
        FollowLineRejected::WrongValue {
            key: key.to_string(),
            reason: reason.to_string(),
        }
    }
}
