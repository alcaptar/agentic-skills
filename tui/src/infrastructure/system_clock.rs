use std::time::Instant;

use crate::domain::clock::Clock;

pub struct SystemClock;

impl Clock for SystemClock {
    fn now(&self) -> Instant {
        Instant::now()
    }
}
