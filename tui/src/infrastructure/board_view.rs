use ratatui::Frame;
use ratatui::layout::{Constraint, Layout};
use ratatui::style::{Color, Style};
use ratatui::text::Line;
use ratatui::widgets::{Block, Paragraph};

use crate::application::queries::read_slice_detail::SliceDetail;
use crate::application::queries::watch_slices::WatchedBoard;
use crate::domain::parent::Parent;
use crate::domain::slice_board::FeatureGroup;
use crate::domain::slice_key::SliceKey;
use crate::infrastructure::detail_view::DetailView;

pub struct BoardView;

impl BoardView {
    pub fn render(
        frame: &mut Frame,
        watched: &WatchedBoard,
        selected: Option<&SliceKey>,
        detail: Option<&SliceDetail>,
    ) {
        let opened = detail.and_then(|detail| watched.board().row(detail.key()).map(|row| (row, detail)));
        let board_area = match opened {
            Some((row, detail)) => {
                let [board_area, detail_area] =
                    Layout::vertical([Constraint::Min(0), Constraint::Percentage(50)]).areas(frame.area());
                DetailView::render(frame, detail_area, row, detail);
                board_area
            }
            None => frame.area(),
        };
        let groups = watched.board().groups();
        let mut constraints: Vec<Constraint> = groups
            .iter()
            .map(|group| Constraint::Length(Self::height_of(group)))
            .collect();
        constraints.push(Constraint::Min(0));
        constraints.push(Constraint::Length(1));
        let areas = Layout::vertical(constraints).split(board_area);

        for (group, area) in groups.iter().zip(areas.iter()) {
            let lines: Vec<Line> = group
                .rows()
                .iter()
                .map(|row| {
                    let marker = if selected == Some(row.key()) { ">" } else { " " };
                    Line::from(format!(
                        "{marker} {}  {}  {}  {}",
                        row.label(),
                        row.slice_id(),
                        row.step(),
                        row.status()
                    ))
                })
                .collect();
            frame.render_widget(
                Paragraph::new(lines).block(Block::bordered().title(Self::title_of(group))),
                *area,
            );
        }

        if let (Some(rejection), Some(area)) = (watched.rejection(), areas.last()) {
            frame.render_widget(
                Paragraph::new(rejection.to_string()).style(Style::new().fg(Color::Red)),
                *area,
            );
        }
    }

    fn height_of(group: &FeatureGroup) -> u16 {
        u16::try_from(group.rows().len()).unwrap_or(u16::MAX).saturating_add(2)
    }

    fn title_of(group: &FeatureGroup) -> String {
        match group.parent() {
            Parent::Issue(issue) => format!("{} #{issue}", group.repo()),
            Parent::Absent => format!("{} no parent", group.repo()),
        }
    }
}
