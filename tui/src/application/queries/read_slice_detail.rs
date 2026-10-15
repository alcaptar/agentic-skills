use crate::domain::slice_key::SliceKey;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SliceDetail {
    key: SliceKey,
}

impl SliceDetail {
    pub fn key(&self) -> &SliceKey {
        &self.key
    }
}

pub struct ReadSliceDetail;

impl ReadSliceDetail {
    pub fn execute(key: SliceKey) -> SliceDetail {
        SliceDetail { key }
    }
}
