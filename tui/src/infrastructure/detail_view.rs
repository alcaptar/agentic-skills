use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::style::{Color, Style};
use ratatui::text::Line;
use ratatui::widgets::{Block, Paragraph};

use crate::application::queries::read_slice_detail::SliceDetail;
use crate::domain::errors::UnderstandingUnread;
use crate::domain::slice_row::SliceRow;
use crate::domain::understanding::Understanding;

pub struct DetailView;

impl DetailView {
    pub fn render(frame: &mut Frame, area: Rect, row: &SliceRow, detail: &SliceDetail) {
        let mut lines: Vec<Line> = row
            .events()
            .iter()
            .map(|event| Line::from(format!("{}  {}", event.step(), event.status())))
            .collect();
        lines.push(Line::from(""));
        lines.extend(Self::understanding_lines(detail.understanding()));
        frame.render_widget(
            Paragraph::new(lines).block(Block::bordered().title(row.label().to_string())),
            area,
        );
    }

    fn understanding_lines(understanding: &Result<Understanding, UnderstandingUnread>) -> Vec<Line<'static>> {
        match understanding {
            Ok(Understanding::Published { text }) => text.lines().map(|line| Line::from(line.to_string())).collect(),
            Ok(Understanding::NotPublished) => vec![Line::from("no understanding published")],
            Err(unread) => vec![Line::from(unread.to_string()).style(Style::new().fg(Color::Red))],
        }
    }
}
