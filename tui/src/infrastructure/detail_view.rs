use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::Line;
use ratatui::widgets::{Block, Paragraph};

use crate::domain::slice_row::SliceRow;

pub struct DetailView;

impl DetailView {
    pub fn render(frame: &mut Frame, area: Rect, row: &SliceRow) {
        let lines: Vec<Line> = row
            .events()
            .iter()
            .map(|event| Line::from(format!("{}  {}", event.step(), event.status())))
            .collect();
        frame.render_widget(
            Paragraph::new(lines).block(Block::bordered().title(row.label().to_string())),
            area,
        );
    }
}
