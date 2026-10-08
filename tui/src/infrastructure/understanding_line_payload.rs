use serde_json::{Map, Value};

use crate::domain::errors::UnderstandingUnread;
use crate::domain::understanding::Understanding;

pub struct UnderstandingLinePayload {
    fields: Map<String, Value>,
}

impl UnderstandingLinePayload {
    pub const KEYS: [&'static str; 2] = ["version", "text"];

    pub fn parsed(raw: &str) -> Result<Understanding, UnderstandingUnread> {
        match serde_json::from_str::<Value>(raw) {
            Ok(Value::Object(fields)) => Self { fields }.to_domain(),
            Ok(_) | Err(_) => Err(UnderstandingUnread::NotJson {
                output: raw.to_string(),
            }),
        }
    }

    fn to_domain(&self) -> Result<Understanding, UnderstandingUnread> {
        if let Some(key) = self.fields.keys().find(|key| !Self::KEYS.contains(&key.as_str())) {
            return Err(Self::wrong(key, "unknown key"));
        }
        self.fields
            .get("version")
            .and_then(Value::as_u64)
            .ok_or_else(|| Self::wrong("version", "expected a whole number"))?;
        let text = self
            .fields
            .get("text")
            .and_then(Value::as_str)
            .ok_or_else(|| Self::wrong("text", "expected a string"))?;

        Ok(Understanding::Published { text: text.to_string() })
    }

    fn wrong(key: &str, reason: &str) -> UnderstandingUnread {
        UnderstandingUnread::WrongValue {
            key: key.to_string(),
            reason: reason.to_string(),
        }
    }
}
