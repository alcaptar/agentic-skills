#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OpenIssue {
    number: u64,
    body: String,
}

impl OpenIssue {
    pub fn new(number: u64, body: &str) -> Self {
        Self {
            number,
            body: body.to_string(),
        }
    }

    pub fn number(&self) -> u64 {
        self.number
    }

    pub fn body(&self) -> &str {
        &self.body
    }
}
