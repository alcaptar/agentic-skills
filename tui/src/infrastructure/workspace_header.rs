use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::style::{Color, Style};
use ratatui::text::Line;
use ratatui::widgets::Paragraph;

use crate::application::queries::bind_workspace::WorkspaceState;
use crate::domain::workspace_binding::WorkspaceBinding;
use crate::domain::workspace_repo::WorkspaceRepo;

pub struct WorkspaceHeader;

impl WorkspaceHeader {
    pub const HEIGHT: u16 = 3;

    pub fn render(frame: &mut Frame, area: Rect, state: &WorkspaceState) {
        let repo = match state.repo() {
            WorkspaceRepo::Known(repo) => repo.as_str(),
            WorkspaceRepo::Unknown => "unknown",
        };
        let feature = match state.binding() {
            WorkspaceBinding::Unbound => "this workspace has no feature yet".to_string(),
            WorkspaceBinding::Bound(parent) => format!("feature #{parent}"),
        };
        let warning = state
            .warning()
            .map(|warning| Line::styled(warning.to_string(), Style::new().fg(Color::Red)))
            .unwrap_or_default();

        frame.render_widget(
            Paragraph::new(vec![
                Line::from(format!("workspace {}  repo {repo}", state.id().as_str())),
                Line::from(feature),
                warning,
            ]),
            area,
        );
    }
}
