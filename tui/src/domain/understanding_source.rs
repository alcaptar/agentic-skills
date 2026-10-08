use crate::domain::errors::UnderstandingUnread;
use crate::domain::slice_key::SliceKey;
use crate::domain::understanding::Understanding;

pub trait UnderstandingSource {
    fn understanding_of(&mut self, key: &SliceKey) -> Result<Understanding, UnderstandingUnread>;
}
