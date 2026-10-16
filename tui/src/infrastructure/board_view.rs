use ratatui::Frame;
use ratatui::layout::{Constraint, Layout, Rect};
use ratatui::style::{Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Paragraph};

use crate::application::queries::read_slice_detail::SliceDetail;
use crate::application::queries::watch_slices::WatchedBoard;
use crate::domain::attention::Attention;
use crate::domain::closure::Closure;
use crate::domain::elapsed::Elapsed;
use crate::domain::parent::Parent;
use crate::domain::slice_board::FeatureGroup;
use crate::domain::slice_key::SliceKey;
use crate::domain::slice_row::SliceRow;
use crate::infrastructure::detail_view::DetailView;
use crate::infrastructure::slice_glyph::SliceGlyph;

pub struct BoardView;

impl BoardView {
    const NAME_WIDTH: usize = 40;
    const KEYS: &'static str = " ↑↓ mover · enter detalle · ctrl+q claude";
    const SEPARATOR: &'static str = " · ";

    pub fn render(
        frame: &mut Frame,
        area: Rect,
        watched: &WatchedBoard,
        selected: Option<&SliceKey>,
        detail: Option<&SliceDetail>,
        now: u64,
    ) {
        if let Some(row) = detail.and_then(|detail| watched.board().row(detail.key())) {
            DetailView::render(frame, area, row, now);
            return;
        }
        let groups = watched.board().groups();
        let painted: Vec<(&FeatureGroup, Vec<Line>)> = groups
            .iter()
            .map(|group| (group, Self::lines_of(group, selected, now)))
            .collect();
        let constraints: Vec<Constraint> = painted
            .iter()
            .enumerate()
            .map(|(index, (_, lines))| {
                if index + 1 == painted.len() {
                    Constraint::Min(0)
                } else {
                    Constraint::Length(u16::try_from(lines.len()).unwrap_or(u16::MAX).saturating_add(2))
                }
            })
            .collect();
        let areas = Layout::vertical(constraints).split(area);
        let mut footer = area;
        for ((group, lines), group_area) in painted.into_iter().zip(areas.iter()) {
            let block = Block::bordered().title(Self::title_of(group));
            footer = block.inner(*group_area);
            frame.render_widget(Paragraph::new(lines).block(block), *group_area);
        }
        Self::render_footer(frame, footer, watched);
    }

    fn render_footer(frame: &mut Frame, area: Rect, watched: &WatchedBoard) {
        if area.height == 0 {
            return;
        }
        let keys_row = Rect::new(area.x, area.y + area.height - 1, area.width, 1);
        frame.render_widget(Paragraph::new(Self::KEYS), keys_row);
        if let (Some(rejection), true) = (watched.rejection(), area.height > 1) {
            let rejection_row = Rect::new(area.x, keys_row.y - 1, area.width, 1);
            frame.render_widget(
                Paragraph::new(format!(" {rejection}")).style(SliceGlyph::alarm()),
                rejection_row,
            );
        }
    }

    fn lines_of(group: &FeatureGroup, selected: Option<&SliceKey>, now: u64) -> Vec<Line<'static>> {
        let mut lines = vec![Line::default()];
        for attention in Attention::ALL {
            let rows = group.rows_in(attention);
            if rows.is_empty() {
                continue;
            }
            lines.push(Line::from(Span::styled(
                format!(" {} ({})", attention.heading(), rows.len()),
                SliceGlyph::heading_style(attention).add_modifier(Modifier::BOLD),
            )));
            for row in rows {
                lines.push(Self::row_line(row, selected == Some(row.key()), now));
                if let (Attention::Running, Some(last)) = (attention, row.activity().last()) {
                    lines.push(Line::from(Span::styled(
                        format!("     {} {}", last.tool(), last.target()),
                        SliceGlyph::quiet(),
                    )));
                }
            }
            lines.push(Line::default());
        }
        lines.pop();

        lines
    }

    fn row_line(row: &SliceRow, selected: bool, now: u64) -> Line<'static> {
        let marker = if selected { ">" } else { " " };
        let mut spans = vec![
            Span::raw(marker),
            SliceGlyph::of(row, now),
            Span::raw(format!(" {} {} ", row.subject().number(), Self::name_of(row))),
        ];
        let parts = Self::summary_of(row, now);
        for (index, part) in parts.into_iter().enumerate() {
            if index > 0 {
                spans.push(Span::raw(Self::SEPARATOR));
            }
            spans.push(part);
        }
        let line = Line::from(spans);
        if selected {
            return line.style(Style::new().add_modifier(Modifier::BOLD));
        }

        line
    }

    fn summary_of(row: &SliceRow, now: u64) -> Vec<Span<'static>> {
        let latest = row.latest();
        let elapsed = Span::raw(Elapsed::between(latest.at(), now).to_string());
        let pull_request = row.pull_request().map(|number| Span::raw(format!("#{number}")));
        let step = Span::raw(latest.step().map_or("", |step| step.name()).to_string());
        match latest.closure() {
            Closure::Pending => vec![Span::raw("pendiente")],
            Closure::InProgress if row.process_is_gone() => {
                vec![step, Span::styled("proceso muerto", SliceGlyph::alarm())]
            }
            Closure::InProgress => {
                let mut parts = vec![step];
                parts.extend(latest.rounds().in_use().into_iter().map(|(counter, round)| {
                    Span::raw(format!("{} {}/{}", counter.label(), round.used(), round.limit()))
                }));
                parts.push(elapsed);
                let spend = latest.spend();
                if spend.nears_the_budget() {
                    parts.push(Span::styled(
                        format!("${:.0}/{:.0}", spend.cost_usd(), spend.budget_usd()),
                        SliceGlyph::warning(),
                    ));
                }
                parts
            }
            Closure::AwaitingMerge | Closure::Merged => {
                let label = Span::raw(latest.closure().label());
                [Some(label), pull_request, Some(elapsed)]
                    .into_iter()
                    .flatten()
                    .collect()
            }
            Closure::Blocked(_) | Closure::Aborted(_) => vec![Span::raw(latest.closure().label()), elapsed],
        }
    }

    fn name_of(row: &SliceRow) -> String {
        let label = row.label();
        if label.chars().count() > Self::NAME_WIDTH {
            let kept: String = label.chars().take(Self::NAME_WIDTH - 1).collect();
            return format!("{kept}…");
        }

        format!("{label:<width$}", width = Self::NAME_WIDTH)
    }

    fn title_of(group: &FeatureGroup) -> String {
        let feature = match group.parent() {
            Parent::Issue(issue) => format!("{} #{issue}", group.repo()),
            Parent::Absent => format!("{} sin padre", group.repo()),
        };

        match group.needing_you() {
            0 => format!(" {feature} "),
            1 => format!(" {feature} · 1 te necesita "),
            count => format!(" {feature} · {count} te necesitan "),
        }
    }
}
