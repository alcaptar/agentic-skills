use std::io;
use std::process::ExitCode;
use std::time::Duration;

use crossterm::event::{self, Event, KeyCode, KeyEvent, KeyEventKind, KeyModifiers};

use crate::application::queries::watch_slices::WatchSlices;
use crate::domain::slice_board::SliceBoard;
use crate::infrastructure::board_view::BoardView;
use crate::infrastructure::endless_follow_process::EndlessFollowProcess;
use crate::infrastructure::terminal_session::TerminalSession;

pub struct Cli;

impl Cli {
    const FOLLOW_ARGV: [&'static str; 3] = ["slice-runner", "follow", "--json"];
    const TICK: Duration = Duration::from_millis(100);

    pub fn main() -> ExitCode {
        match Self::run() {
            Ok(()) => ExitCode::SUCCESS,
            Err(error) => {
                eprintln!("slice-runner-tui: {error}");
                ExitCode::FAILURE
            }
        }
    }

    fn run() -> Result<(), String> {
        let source = EndlessFollowProcess::spawn(&Self::FOLLOW_ARGV).map_err(|rejected| rejected.to_string())?;
        let mut watch = WatchSlices::new(source);
        let mut session = TerminalSession::open().map_err(|error| error.to_string())?;
        let mut board = SliceBoard::empty();
        loop {
            let watched = watch.execute(board);
            session
                .terminal()
                .draw(|frame| BoardView::render(frame, &watched))
                .map_err(|error| error.to_string())?;
            if Self::quit_requested().map_err(|error| error.to_string())? {
                return Ok(());
            }
            board = watched.into_board();
        }
    }

    fn quit_requested() -> io::Result<bool> {
        if !event::poll(Self::TICK)? {
            return Ok(false);
        }

        Ok(match event::read()? {
            Event::Key(key) => Self::is_quit(key),
            Event::FocusGained | Event::FocusLost | Event::Mouse(_) | Event::Paste(_) | Event::Resize(_, _) => false,
        })
    }

    fn is_quit(key: KeyEvent) -> bool {
        key.kind == KeyEventKind::Press
            && (key.code == KeyCode::Char('q')
                || (key.code == KeyCode::Char('c') && key.modifiers.contains(KeyModifiers::CONTROL)))
    }
}
