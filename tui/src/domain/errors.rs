use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FollowLineRejected {
    NotJson { line: String },
    WrongValue { key: String, reason: String },
    FollowEnded,
    FollowNotLaunched { reason: String },
}

impl fmt::Display for FollowLineRejected {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotJson { line } => write!(formatter, "line is not a JSON object: {line}"),
            Self::WrongValue { key, reason } => write!(formatter, "wrong value for `{key}`: {reason}"),
            Self::FollowEnded => write!(formatter, "slice-runner follow ended"),
            Self::FollowNotLaunched { reason } => write!(formatter, "could not launch slice-runner follow: {reason}"),
        }
    }
}
