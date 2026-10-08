use crate::domain::understanding::Understanding;

pub struct UnderstandingMother;

impl UnderstandingMother {
    pub const TEXT: &'static str = "El contador vive en Run y no en el conductor.\n\nSegunda linea tras un parrafo.";

    pub fn published() -> Understanding {
        Understanding::Published {
            text: Self::TEXT.to_string(),
        }
    }

    pub fn not_published() -> Understanding {
        Understanding::NotPublished
    }
}
