use std::path::{Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SessionLaunch {
    argv: Vec<String>,
    directory: PathBuf,
    environment: Vec<(String, String)>,
}

impl SessionLaunch {
    pub fn new(argv: Vec<String>, directory: PathBuf, environment: Vec<(String, String)>) -> Self {
        Self {
            argv,
            directory,
            environment,
        }
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
