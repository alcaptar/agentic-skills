use std::collections::BTreeMap;

use crate::domain::follow_line::FollowLine;
use crate::domain::parent::Parent;
use crate::domain::slice_row::SliceRow;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FeatureGroup {
    repo: String,
    parent: Parent,
    rows: Vec<SliceRow>,
}

impl FeatureGroup {
    pub fn repo(&self) -> &str {
        &self.repo
    }

    pub fn parent(&self) -> Parent {
        self.parent
    }

    pub fn rows(&self) -> &[SliceRow] {
        &self.rows
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SliceBoard {
    rows: Vec<SliceRow>,
}

impl SliceBoard {
    pub fn empty() -> Self {
        Self { rows: Vec::new() }
    }

    pub fn with_line(mut self, line: FollowLine) -> Self {
        match self.rows.iter().position(|row| row.is_the_slice_of(&line)) {
            Some(index) => self.rows[index] = self.rows[index].with_line(line),
            None => self.rows.push(SliceRow::first(line)),
        }

        self
    }

    pub fn groups(&self) -> Vec<FeatureGroup> {
        let mut grouped: BTreeMap<(String, Parent), Vec<SliceRow>> = BTreeMap::new();
        for row in &self.rows {
            grouped
                .entry((row.repo().to_string(), row.parent()))
                .or_default()
                .push(row.clone());
        }

        grouped
            .into_iter()
            .map(|((repo, parent), rows)| FeatureGroup { repo, parent, rows })
            .collect()
    }
}
