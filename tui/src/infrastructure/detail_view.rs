use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Paragraph};

use crate::domain::activity_line::Actor;
use crate::domain::closure::Closure;
use crate::domain::elapsed::Elapsed;
use crate::domain::rounds::Counter;
use crate::domain::slice_row::SliceRow;
use crate::domain::step::Step;
use crate::domain::transition::Transition;
use crate::infrastructure::narration::Narration;
use crate::infrastructure::slice_glyph::SliceGlyph;

pub struct DetailView;

impl DetailView {
    const KEYS: &'static str = " esc volver · ctrl+q claude";
    const SHOWN_ACTIVITY: usize = 5;
    const SENTENCE_WIDTH: usize = 55;
    const PHASES: [(Step, &'static str); 7] = [
        (Step::MountWorktree, "mnt"),
        (Step::Implement, "imp"),
        (Step::RunControls, "ctl"),
        (Step::Verify, "ver"),
        (Step::OpenPullRequest, "pr"),
        (Step::AwaitCi, "ci"),
        (Step::AwaitMerge, "mrg"),
    ];
    const FIRST_COUNTERS: [Counter; 3] = [Counter::Controls, Counter::Hygiene, Counter::Judge];
    const LAST_COUNTERS: [Counter; 3] = [Counter::Ci, Counter::CiIndeterminate, Counter::CatchUp];

    pub fn render(frame: &mut Frame, area: Rect, row: &SliceRow, now: u64) {
        let block = Block::bordered().title(format!(" {} {} ", row.subject().number(), row.label()));
        let inner = block.inner(area);
        let room = usize::from(inner.height.saturating_sub(1));
        let top = Self::top_of(row, now);
        let bottom = Self::bottom_of(row);
        let history = Self::history_of(row, now);
        let space = room.saturating_sub(top.len() + bottom.len() + 1);
        let skipped = history.len().saturating_sub(space);
        let mut lines = top;
        lines.push(Line::from(" HISTORIA"));
        lines.extend(history.into_iter().skip(skipped));
        lines.extend(bottom);
        frame.render_widget(Paragraph::new(lines).block(block), area);
        if inner.height > 0 {
            let keys_row = Rect::new(inner.x, inner.y + inner.height - 1, inner.width, 1);
            frame.render_widget(Paragraph::new(Self::KEYS), keys_row);
        }
    }

    fn top_of(row: &SliceRow, now: u64) -> Vec<Line<'static>> {
        let mut lines = vec![Self::headline_of(row, now), Self::spend_of(row), Line::default()];
        lines.push(Line::from(Self::phases_of(row)));
        lines.push(Line::from(Self::counters_of(row, &Self::FIRST_COUNTERS)));
        lines.push(Line::from(Self::counters_of(row, &Self::LAST_COUNTERS)));
        lines.push(Line::default());
        if row.is_running() && !row.activity().is_empty() {
            lines.extend(Self::activity_of(row, now));
            lines.push(Line::default());
        }

        lines
    }

    fn headline_of(row: &SliceRow, now: u64) -> Line<'static> {
        let latest = row.latest();
        let closure = latest.closure();
        let mut spans = vec![Span::raw(" "), SliceGlyph::of(row, now), Span::raw(" ")];
        if closure == Closure::Pending {
            spans.push(Span::raw(closure.label()));
            return Line::from(spans);
        }
        spans.push(Span::raw(closure.label()));
        if row.process_is_gone() {
            spans.push(Span::raw(" · "));
            spans.push(Span::styled("proceso muerto", SliceGlyph::alarm()));
        }
        if let Some(step) = latest.step() {
            spans.push(Span::raw(format!(" · {}", step.name())));
        }
        let first = row.transitions().first().map_or(latest.at(), Transition::at);
        let end = match closure {
            Closure::Blocked(_) | Closure::Aborted(_) | Closure::Merged => latest.at(),
            Closure::Pending | Closure::InProgress | Closure::AwaitingMerge => now,
        };
        spans.push(Span::raw(format!(
            " · hace {} · {} en total",
            Elapsed::between(latest.at(), now),
            Elapsed::between(first, end)
        )));

        Line::from(spans)
    }

    fn spend_of(row: &SliceRow) -> Line<'static> {
        let spend = row.latest().spend();
        let pull_request = row.pull_request().map_or_else(
            || "sin pull request".to_string(),
            |number| format!("pull request #{number}"),
        );
        let amount = format!(" ${:.2} de ${:.0}", spend.cost_usd(), spend.budget_usd());
        let amount = if spend.nears_the_budget() {
            Span::styled(amount, SliceGlyph::warning())
        } else {
            Span::raw(amount)
        };

        Line::from(vec![amount, Span::raw(format!(" · {pull_request}"))])
    }

    fn phases_of(row: &SliceRow) -> String {
        let latest = row.latest();
        let reached_later = row
            .transitions()
            .iter()
            .any(|transition| transition.step().is_some_and(|step| step != Step::MountWorktree));
        let phases: Vec<String> = Self::PHASES
            .iter()
            .map(|(step, abbreviation)| {
                let visits = row
                    .transitions()
                    .iter()
                    .filter(|transition| {
                        transition.step() == Some(*step) && transition.closure() == Closure::InProgress
                    })
                    .count();
                let mark = if latest.step() == Some(*step) {
                    Self::current_mark(latest.closure())
                } else if visits > 0 || (*step == Step::MountWorktree && reached_later) {
                    "■"
                } else {
                    "·"
                };
                format!("{abbreviation} {mark}{}", Self::superscript(visits))
            })
            .collect();

        format!(" {}", phases.join("  "))
    }

    fn current_mark(closure: Closure) -> &'static str {
        match closure {
            Closure::InProgress => "▶",
            Closure::AwaitingMerge => "◆",
            Closure::Blocked(_) | Closure::Aborted(_) => "✕",
            Closure::Merged => "✓",
            Closure::Pending => "·",
        }
    }

    fn superscript(visits: usize) -> &'static str {
        match visits {
            0 | 1 => "",
            2 => "²",
            3 => "³",
            4 => "⁴",
            5 => "⁵",
            6 => "⁶",
            7 => "⁷",
            8 => "⁸",
            9 => "⁹",
            _ => "⁺",
        }
    }

    fn counters_of(row: &SliceRow, counters: &[Counter]) -> String {
        let rounds = row.latest().rounds();
        let shown: Vec<String> = counters
            .iter()
            .map(|counter| {
                let round = rounds.of(*counter);
                format!("{} {}/{}", counter.label(), round.used(), round.limit())
            })
            .collect();

        format!(" {}", shown.join(" · "))
    }

    fn activity_of(row: &SliceRow, now: u64) -> Vec<Line<'static>> {
        let activity = row.activity();
        let Some(last) = activity.last() else {
            return Vec::new();
        };
        let heading = match last.actor() {
            Actor::Implementer => " QUÉ HACE EL IMPLEMENTADOR AHORA",
            Actor::Judge => " QUÉ HACE EL JUEZ AHORA",
            Actor::Controls => " QUÉ HACEN LOS CONTROLES AHORA",
        };
        let mut lines = vec![Line::from(heading)];
        let start = activity.len().saturating_sub(Self::SHOWN_ACTIVITY);
        lines.extend(activity[start..].iter().map(|line| {
            Line::from(format!(
                " hace {:<4} {:<5} {}",
                Elapsed::between(line.at(), now).to_string(),
                line.tool(),
                line.target()
            ))
        }));

        lines
    }

    fn history_of(row: &SliceRow, now: u64) -> Vec<Line<'static>> {
        let transitions = row.transitions();
        let running = row.is_running() && !row.process_is_gone();
        transitions
            .iter()
            .enumerate()
            .map(|(index, transition)| {
                let earlier = index.checked_sub(1).and_then(|before| transitions.get(before));
                let later = transitions.get(index + 1);
                let mut sentence = Narration::of(transition, earlier);
                if later.is_none() && running {
                    sentence = format!("{} {sentence}", SliceGlyph::spinner(now));
                }
                let duration = later.map_or_else(String::new, |later| {
                    Elapsed::between(transition.at(), later.at()).to_string()
                });
                let age = Elapsed::between(transition.at(), now).to_string();
                if duration.is_empty() {
                    return Line::from(format!(" hace {age:<4} {sentence}"));
                }

                Line::from(format!(
                    " hace {age:<4} {sentence:<width$}{duration}",
                    width = Self::SENTENCE_WIDTH
                ))
            })
            .collect()
    }

    fn bottom_of(row: &SliceRow) -> Vec<Line<'static>> {
        match row.latest().closure() {
            Closure::Blocked(_) | Closure::Aborted(_) => vec![
                Line::default(),
                Line::from(" Para reabrirla:"),
                Line::from(format!(
                    " slice-runner retry {} --repo {} \"<instrucción>\"",
                    row.subject().issue(),
                    row.repo()
                )),
            ],
            Closure::Pending | Closure::InProgress | Closure::AwaitingMerge | Closure::Merged => Vec::new(),
        }
    }
}
