use std::io;
use std::process::ExitCode;
use std::time::Duration;

use crossterm::event::{self, Event, KeyCode, KeyEvent, KeyEventKind, KeyModifiers};

use crate::application::queries::read_slice_detail::{ReadSliceDetail, SliceDetail};
use crate::application::queries::watch_slices::WatchSlices;
use crate::domain::slice_board::SliceBoard;
use crate::domain::slice_key::SliceKey;
use crate::infrastructure::board_view::BoardView;
use crate::infrastructure::bounded_understanding_process::BoundedUnderstandingProcess;
use crate::infrastructure::endless_follow_process::EndlessFollowProcess;
use crate::infrastructure::terminal_session::TerminalSession;

#[derive(Clone, Copy)]
enum Order {
    Quit,
    Previous,
    Next,
    Open,
    Close,
    Nothing,
}

pub struct Cli;

impl Cli {
    const PROGRAM: &'static str = "slice-runner";
    const FOLLOW_ARGV: [&'static str; 3] = [Self::PROGRAM, "follow", "--json"];
    const TICK: Duration = Duration::from_millis(100);
    const UNDERSTANDING_BUDGET: Duration = Duration::from_secs(10);
    const BINDINGS: [(KeyCode, Order); 7] = [
        (KeyCode::Char('q'), Order::Quit),
        (KeyCode::Up, Order::Previous),
        (KeyCode::Char('k'), Order::Previous),
        (KeyCode::Down, Order::Next),
        (KeyCode::Char('j'), Order::Next),
        (KeyCode::Enter, Order::Open),
        (KeyCode::Esc, Order::Close),
    ];

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
        let mut read = ReadSliceDetail::new(BoundedUnderstandingProcess::new(
            vec![Self::PROGRAM.to_string()],
            Self::UNDERSTANDING_BUDGET,
        ));
        let mut board = SliceBoard::empty();
        let mut selected: Option<SliceKey> = None;
        let mut detail: Option<SliceDetail> = None;
        loop {
            let watched = watch.execute(board);
            session
                .terminal()
                .draw(|frame| BoardView::render(frame, &watched, selected.as_ref(), detail.as_ref()))
                .map_err(|error| error.to_string())?;
            match Self::next_order().map_err(|error| error.to_string())? {
                Order::Quit => return Ok(()),
                Order::Previous => {
                    let target = watched.board().before(selected.as_ref());
                    Self::moved(&mut selected, target, &mut detail);
                }
                Order::Next => {
                    let target = watched.board().after(selected.as_ref());
                    Self::moved(&mut selected, target, &mut detail);
                }
                Order::Open => {
                    if let Some(key) = selected.clone() {
                        detail = Some(read.execute(key));
                    }
                }
                Order::Close => detail = None,
                Order::Nothing => {}
            }
            board = watched.into_board();
        }
    }

    fn moved(selected: &mut Option<SliceKey>, target: Option<SliceKey>, detail: &mut Option<SliceDetail>) {
        if target.is_some() && target != *selected {
            *detail = None;
            *selected = target;
        }
    }

    fn next_order() -> io::Result<Order> {
        if !event::poll(Self::TICK)? {
            return Ok(Order::Nothing);
        }

        Ok(match event::read()? {
            Event::Key(key) => Self::order_of(key),
            Event::FocusGained | Event::FocusLost | Event::Mouse(_) | Event::Paste(_) | Event::Resize(_, _) => {
                Order::Nothing
            }
        })
    }

    fn order_of(key: KeyEvent) -> Order {
        if key.kind != KeyEventKind::Press {
            return Order::Nothing;
        }
        if key.code == KeyCode::Char('c') && key.modifiers.contains(KeyModifiers::CONTROL) {
            return Order::Quit;
        }

        Self::BINDINGS
            .iter()
            .find(|(code, _)| *code == key.code)
            .map_or(Order::Nothing, |(_, order)| *order)
    }
}
