use std::io::{self, stdout};

use crossterm::event::{DisableBracketedPaste, EnableBracketedPaste};
use crossterm::execute;
use ratatui::DefaultTerminal;

pub struct TerminalSession {
    terminal: DefaultTerminal,
}

impl TerminalSession {
    pub fn open() -> io::Result<Self> {
        let terminal = ratatui::try_init()?;
        if let Err(error) = execute!(stdout(), EnableBracketedPaste) {
            ratatui::restore();
            return Err(error);
        }

        Ok(Self { terminal })
    }

    pub fn terminal(&mut self) -> &mut DefaultTerminal {
        &mut self.terminal
    }
}

impl Drop for TerminalSession {
    fn drop(&mut self) {
        execute!(stdout(), DisableBracketedPaste).ok();
        ratatui::restore();
    }
}
