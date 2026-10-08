use crate::domain::errors::FollowLineRejected;
use crate::domain::follow_line::FollowLine;

pub trait FollowSource {
    fn pending(&mut self) -> Vec<Result<FollowLine, FollowLineRejected>>;
}
