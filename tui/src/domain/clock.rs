use std::time::Instant;

pub trait Clock: Send {
    fn now(&self) -> Instant;
}
