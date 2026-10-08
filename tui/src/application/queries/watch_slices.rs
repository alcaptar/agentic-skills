use crate::domain::errors::FollowLineRejected;
use crate::domain::follow_source::FollowSource;
use crate::domain::slice_board::SliceBoard;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WatchedBoard {
    board: SliceBoard,
    rejection: Option<FollowLineRejected>,
}

impl WatchedBoard {
    pub fn board(&self) -> &SliceBoard {
        &self.board
    }

    pub fn rejection(&self) -> Option<&FollowLineRejected> {
        self.rejection.as_ref()
    }

    pub fn into_board(self) -> SliceBoard {
        self.board
    }
}

pub struct WatchSlices<S: FollowSource> {
    source: S,
    rejection: Option<FollowLineRejected>,
}

impl<S: FollowSource> WatchSlices<S> {
    pub fn new(source: S) -> Self {
        Self {
            source,
            rejection: None,
        }
    }

    pub fn execute(&mut self, board: SliceBoard) -> WatchedBoard {
        let mut board = board;
        for delivery in self.source.pending() {
            match delivery {
                Ok(line) => {
                    board = board.with_line(line);
                    self.rejection = None;
                }
                Err(rejection) => self.rejection = Some(rejection),
            }
        }

        WatchedBoard {
            board,
            rejection: self.rejection.clone(),
        }
    }
}
