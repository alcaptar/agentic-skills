use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::style::{Color, Style};
use ratatui::widgets::Block;
use tui_term::widget::PseudoTerminal;

use crate::infrastructure::endless_pty_session::EndlessPtySession;

pub struct ClaudePane;

impl ClaudePane {
    const FOCUSED_BORDER: Color = Color::Cyan;

    pub fn render(frame: &mut Frame, area: Rect, session: &mut EndlessPtySession, focused: bool) {
        let title = if session.has_ended() {
            "claude session ended"
        } else {
            "claude"
        };
        let border = if focused {
            Style::new().fg(Self::FOCUSED_BORDER)
        } else {
            Style::new()
        };
        let block = Block::bordered().title(title).border_style(border);
        session.with_screen(|screen| frame.render_widget(PseudoTerminal::new(screen).block(block), area));
    }
}
