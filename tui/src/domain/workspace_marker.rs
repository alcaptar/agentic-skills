use crate::domain::workspace_id::WorkspaceId;

pub struct WorkspaceMarker;

impl WorkspaceMarker {
    const OPENING: &'static str = "<!-- slice-runner:workspace ";
    const CLOSING: &'static str = " -->";

    pub fn ends(body: &str, id: &WorkspaceId) -> bool {
        let last_line = body.lines().rev().map(str::trim).find(|line| !line.is_empty());

        last_line == Some(format!("{}{}{}", Self::OPENING, id.as_str(), Self::CLOSING).as_str())
    }
}
