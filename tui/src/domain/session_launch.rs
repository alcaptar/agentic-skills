use std::path::{Path, PathBuf};

use crate::domain::workspace_id::WorkspaceId;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SessionLaunch {
    workspace: WorkspaceId,
    argv: Vec<String>,
    directory: PathBuf,
    environment: Vec<(String, String)>,
}

impl SessionLaunch {
    pub fn new(
        workspace: WorkspaceId,
        argv: Vec<String>,
        directory: PathBuf,
        environment: Vec<(String, String)>,
    ) -> Self {
        Self {
            workspace,
            argv,
            directory,
            environment,
        }
    }

    pub fn workspace(&self) -> &WorkspaceId {
        &self.workspace
    }

    pub fn argv(&self) -> &[String] {
        &self.argv
    }

    pub fn directory(&self) -> &Path {
        &self.directory
    }

    pub fn environment(&self) -> &[(String, String)] {
        &self.environment
    }
}
