use std::io;
use std::process::ExitCode;
use std::time::Duration;

use crossterm::event::{self, Event, KeyEvent};
use ratatui::layout::{Constraint, Layout, Rect};

use crate::application::actions::start_claude_session::{StartClaudeSession, StartClaudeSessionParams};
use crate::application::queries::bind_workspace::BindWorkspace;
use crate::application::queries::read_slice_detail::{ReadSliceDetail, SliceDetail};
use crate::application::queries::watch_slices::WatchSlices;
use crate::domain::binding_cadence::BindingCadence;
use crate::domain::pane_size::PaneSize;
use crate::domain::slice_board::SliceBoard;
use crate::domain::slice_key::SliceKey;
use crate::infrastructure::board_view::BoardView;
use crate::infrastructure::bounded_gh_process::BoundedGhProcess;
use crate::infrastructure::bounded_understanding_process::BoundedUnderstandingProcess;
use crate::infrastructure::claude_pane::ClaudePane;
use crate::infrastructure::endless_follow_process::EndlessFollowProcess;
use crate::infrastructure::endless_pty_session::EndlessPtySession;
use crate::infrastructure::key_bytes::KeyBytes;
use crate::infrastructure::key_routing::{Focus, KeyRouting, Order, Routed};
use crate::infrastructure::random_workspace_ids::RandomWorkspaceIds;
use crate::infrastructure::split_screen::SplitScreen;
use crate::infrastructure::system_clock::SystemClock;
use crate::infrastructure::terminal_session::TerminalSession;
use crate::infrastructure::threaded_workspace_binding::ThreadedWorkspaceBinding;
use crate::infrastructure::workspace_header::WorkspaceHeader;

enum Input {
    Key(KeyEvent),
    Paste(String),
    Resized(PaneSize),
    Nothing,
}

pub struct Cli;

impl Cli {
    const PROGRAM: &'static str = "slice-runner";
    const FOLLOW_ARGV: [&'static str; 3] = [Self::PROGRAM, "follow", "--json"];
    const TICK: Duration = Duration::from_millis(100);
    const UNDERSTANDING_BUDGET: Duration = Duration::from_secs(10);
    const GH_PROGRAM: &'static str = "gh";
    const GH_BUDGET: Duration = Duration::from_secs(10);
    const BINDING_INTERVAL: Duration = Duration::from_secs(5);
    const BINDING_LIMIT: usize = 20;

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
        let window = session.terminal().size().map_err(|error| error.to_string())?;
        let directory = std::env::current_dir().map_err(|error| error.to_string())?;
        let launch =
            StartClaudeSession::new(RandomWorkspaceIds).execute(StartClaudeSessionParams::in_directory(directory));
        let mut claude = EndlessPtySession::spawn(&launch, SplitScreen::pane_size(Rect::from(window)))
            .map_err(|rejected| rejected.to_string())?;
        let mut binding = ThreadedWorkspaceBinding::start(
            BindWorkspace::new(
                BoundedGhProcess::new(vec![Self::GH_PROGRAM.to_string()], Self::GH_BUDGET),
                SystemClock,
                BindingCadence::new(Self::BINDING_INTERVAL, Self::BINDING_LIMIT),
                launch.workspace().clone(),
            ),
            Self::BINDING_INTERVAL,
        );
        let mut read = ReadSliceDetail::new(BoundedUnderstandingProcess::new(
            vec![Self::PROGRAM.to_string()],
            Self::UNDERSTANDING_BUDGET,
        ));
        let mut focus = Focus::Claude;
        let mut board = SliceBoard::empty();
        let mut selected: Option<SliceKey> = None;
        let mut detail: Option<SliceDetail> = None;
        loop {
            let workspace = binding.latest();
            let watched = watch.execute(board);
            let shown = watched.shown_for(&workspace);
            session
                .terminal()
                .draw(|frame| {
                    let (claude_area, board_area) = SplitScreen::areas(frame.area());
                    ClaudePane::render(frame, claude_area, &mut claude, focus == Focus::Claude);
                    let [header_area, slices_area] =
                        Layout::vertical([Constraint::Length(WorkspaceHeader::HEIGHT), Constraint::Min(0)])
                            .areas(board_area);
                    WorkspaceHeader::render(frame, header_area, &workspace);
                    BoardView::render(frame, slices_area, &shown, selected.as_ref(), detail.as_ref());
                })
                .map_err(|error| error.to_string())?;
            match Self::next_input().map_err(|error| error.to_string())? {
                Input::Resized(size) => claude.resize(size),
                Input::Paste(text) => {
                    if focus == Focus::Claude {
                        claude.write(&claude.with_screen(|screen| KeyBytes::of_paste(&text, screen)));
                    }
                }
                Input::Key(key) => match claude.with_screen(|screen| KeyRouting::route(focus, key, screen)) {
                    Routed::ToClaude(bytes) => claude.write(&bytes),
                    Routed::ToggleFocus => focus = focus.toggled(),
                    Routed::Board(Order::Quit) => return Ok(()),
                    Routed::Board(Order::Previous) => {
                        let target = shown.board().before(selected.as_ref());
                        Self::moved(&mut selected, target, &mut detail);
                    }
                    Routed::Board(Order::Next) => {
                        let target = shown.board().after(selected.as_ref());
                        Self::moved(&mut selected, target, &mut detail);
                    }
                    Routed::Board(Order::Open) => {
                        if let Some(key) = selected.clone() {
                            detail = Some(read.execute(key));
                        }
                    }
                    Routed::Board(Order::Close) => detail = None,
                    Routed::Ignored | Routed::Board(Order::Nothing) => {}
                },
                Input::Nothing => {}
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

    fn next_input() -> io::Result<Input> {
        if !event::poll(Self::TICK)? {
            return Ok(Input::Nothing);
        }

        Ok(match event::read()? {
            Event::Key(key) => Input::Key(key),
            Event::Paste(text) => Input::Paste(text),
            Event::Resize(columns, rows) => Input::Resized(SplitScreen::pane_size(Rect::new(0, 0, columns, rows))),
            Event::FocusGained | Event::FocusLost | Event::Mouse(_) => Input::Nothing,
        })
    }
}
