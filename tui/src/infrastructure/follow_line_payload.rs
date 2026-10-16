use serde_json::{Map, Value};

use crate::domain::closing_reason::ClosingReason;
use crate::domain::closure::Closure;
use crate::domain::errors::FollowLineRejected;
use crate::domain::follow_line::FollowLine;
use crate::domain::parent::Parent;
use crate::domain::standing::Standing;
use crate::domain::step::Step;

pub struct FollowLinePayload {
    fields: Map<String, Value>,
}

impl FollowLinePayload {
    pub const REQUIRED_KEYS: [&'static str; 5] = ["repo", "issue", "slice_id", "step", "status"];

    #[cfg(test)]
    pub fn parsed(raw: &str) -> Result<FollowLine, FollowLineRejected> {
        Self::read(raw)?.ok_or_else(|| Self::wrong("kind", "an activity line is not a transition"))
    }

    pub fn delivery(raw: &str) -> Option<Result<FollowLine, FollowLineRejected>> {
        Self::read(raw).transpose()
    }

    fn read(raw: &str) -> Result<Option<FollowLine>, FollowLineRejected> {
        match serde_json::from_str::<Value>(raw) {
            Ok(Value::Object(fields)) => Self { fields }.to_domain(),
            Ok(_) | Err(_) => Err(FollowLineRejected::NotJson { line: raw.to_string() }),
        }
    }

    fn to_domain(&self) -> Result<Option<FollowLine>, FollowLineRejected> {
        match self.optional_number("version")?.unwrap_or(1) {
            1 => self.version_1().map(Some),
            2 => self.version_2(),
            version => Err(FollowLineRejected::UnsupportedVersion { version }),
        }
    }

    fn version_2(&self) -> Result<Option<FollowLine>, FollowLineRejected> {
        match self.required_text("kind")? {
            "transition" => self.transition().map(Some),
            "activity" => Ok(None),
            kind => Err(FollowLineRejected::UnknownKind { kind: kind.to_string() }),
        }
    }

    fn transition(&self) -> Result<FollowLine, FollowLineRejected> {
        let standing = Standing::parse(self.required_text("standing")?)
            .ok_or_else(|| Self::wrong("standing", "not a known standing"))?;
        let reason = match self.optional_text("reason")? {
            Some(text) => Some(ClosingReason::parse(text).ok_or_else(|| Self::wrong("reason", "not a known reason"))?),
            None => None,
        };
        let closure =
            Closure::of(standing, reason).ok_or_else(|| Self::wrong("reason", "does not belong with the standing"))?;
        let step = match self.optional_text("step")? {
            Some(text) => Some(Step::parse(text).ok_or_else(|| Self::wrong("step", "not a known step"))?),
            None => None,
        };

        Ok(FollowLine::transition(
            self.required_text("repo")?,
            self.required_number("issue")?,
            self.required_text("slice_id")?,
            step,
            closure,
            self.parent()?,
            self.optional_text("name")?,
        ))
    }

    fn parent(&self) -> Result<Parent, FollowLineRejected> {
        Ok(match self.optional_number("parent")? {
            Some(issue) => Parent::Issue(issue),
            None => Parent::Absent,
        })
    }

    fn version_1(&self) -> Result<FollowLine, FollowLineRejected> {
        if let Some(key) = Self::REQUIRED_KEYS
            .into_iter()
            .find(|key| !self.fields.contains_key(*key))
        {
            return Err(Self::wrong(key, "required key is missing"));
        }
        Ok(FollowLine::new(
            self.required_text("repo")?,
            self.required_number("issue")?,
            self.required_text("slice_id")?,
            self.required_text("step")?,
            self.required_text("status")?,
            self.parent()?,
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
