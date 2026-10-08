use std::fmt;
use std::time::Duration;

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

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum UnderstandingUnread {
    TimedOut { budget: Duration },
    CommandFailed { reason: String },
    NotJson { output: String },
    WrongValue { key: String, reason: String },
}

impl fmt::Display for UnderstandingUnread {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::TimedOut { budget } => {
                write!(formatter, "slice-runner understanding did not finish within {budget:?}")
            }
            Self::CommandFailed { reason } => write!(formatter, "slice-runner understanding failed: {reason}"),
            Self::NotJson { output } => write!(formatter, "understanding is not a JSON object: {output}"),
            Self::WrongValue { key, reason } => write!(formatter, "wrong value for `{key}`: {reason}"),
        }
    }
}
