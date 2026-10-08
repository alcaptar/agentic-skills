use std::collections::BTreeMap;

use crate::domain::follow_line::FollowLine;
use crate::domain::parent::Parent;
use crate::domain::slice_key::SliceKey;
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

    pub fn row(&self, key: &SliceKey) -> Option<&SliceRow> {
        self.rows.iter().find(|row| row.key() == key)
    }

    pub fn after(&self, current: Option<&SliceKey>) -> Option<SliceKey> {
        let keys = self.keys_in_painted_order();
        match Self::position_of(&keys, current) {
            Some(index) => keys.get(index + 1).or_else(|| keys.get(index)).cloned(),
            None => keys.first().cloned(),
        }
    }

    pub fn before(&self, current: Option<&SliceKey>) -> Option<SliceKey> {
        let keys = self.keys_in_painted_order();
        match Self::position_of(&keys, current) {
            Some(index) => keys.get(index.saturating_sub(1)).cloned(),
            None => keys.first().cloned(),
        }
    }

    fn keys_in_painted_order(&self) -> Vec<SliceKey> {
        self.groups()
            .iter()
            .flat_map(|group| group.rows().iter().map(|row| row.key().clone()).collect::<Vec<_>>())
            .collect()
    }

    fn position_of(keys: &[SliceKey], current: Option<&SliceKey>) -> Option<usize> {
        current.and_then(|current| keys.iter().position(|key| key == current))
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
