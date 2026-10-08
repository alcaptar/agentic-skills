#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Understanding {
    Published { text: String },
    NotPublished,
}
