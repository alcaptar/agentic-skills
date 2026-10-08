use crate::domain::errors::UnderstandingUnread;
use crate::domain::slice_key::SliceKey;
use crate::domain::understanding::Understanding;
use crate::domain::understanding_source::UnderstandingSource;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SliceDetail {
    key: SliceKey,
    understanding: Result<Understanding, UnderstandingUnread>,
}

impl SliceDetail {
    pub fn key(&self) -> &SliceKey {
        &self.key
    }

    pub fn understanding(&self) -> &Result<Understanding, UnderstandingUnread> {
        &self.understanding
    }
}

pub struct ReadSliceDetail<U: UnderstandingSource> {
    source: U,
}

impl<U: UnderstandingSource> ReadSliceDetail<U> {
    pub fn new(source: U) -> Self {
        Self { source }
    }

    pub fn execute(&mut self, key: SliceKey) -> SliceDetail {
        let understanding = self.source.understanding_of(&key);

        SliceDetail { key, understanding }
    }
}
