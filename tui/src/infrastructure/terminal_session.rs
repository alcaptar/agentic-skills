use std::io;

use ratatui::DefaultTerminal;

pub struct TerminalSession {
    terminal: DefaultTerminal,
}

impl TerminalSession {
    pub fn open() -> io::Result<Self> {
        Ok(Self {
            terminal: ratatui::try_init()?,
        })
    }

    pub fn terminal(&mut self) -> &mut DefaultTerminal {
        &mut self.terminal
    }
}

impl Drop for TerminalSession {
    fn drop(&mut self) {
        ratatui::restore();
    }
}
