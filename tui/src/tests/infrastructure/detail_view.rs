use ratatui::Terminal;
use ratatui::backend::TestBackend;

use crate::application::queries::read_slice_detail::{ReadSliceDetail, SliceDetail};
use crate::domain::errors::UnderstandingUnread;
use crate::domain::follow_line::FollowLine;
use crate::domain::slice_row::SliceRow;
use crate::domain::understanding::Understanding;
use crate::infrastructure::detail_view::DetailView;
use crate::tests::application::watching::Watching;
use crate::tests::doubles::ScriptedUnderstandingSource;
use crate::tests::mothers::follow_line_mother::FollowLineMother;

pub struct DetailScreen;

impl DetailScreen {
    pub fn lines_of_one_slice_and_one_of_another() -> Vec<FollowLine> {
        let first = FollowLineMother::moved_to(&FollowLineMother::child_of(140, 150), "event-1");

        vec![
            first.clone(),
            FollowLineMother::orphan(170),
            FollowLineMother::moved_to(&first, "event-2"),
            FollowLineMother::moved_to(&first, "event-3"),
        ]
    }

    pub fn with_answer(answer: Result<Understanding, UnderstandingUnread>) -> String {
        let watched = Watching::one_tick(Watching::lines(Self::lines_of_one_slice_and_one_of_another()));
        let (source, _) = ScriptedUnderstandingSource::answering(answer);
        let detail = ReadSliceDetail::new(source).execute(Watching::key(150));
        let row = watched.board().row(&Watching::key(150)).unwrap();

        Self::text_of(row, &detail)
    }

    pub fn text_of(row: &SliceRow, detail: &SliceDetail) -> String {
        let mut terminal = Terminal::new(TestBackend::new(100, 24)).unwrap();
        terminal
            .draw(|frame| DetailView::render(frame, frame.area(), row, detail))
            .unwrap();

        terminal
            .backend()
            .buffer()
            .content()
            .iter()
            .map(ratatui::buffer::Cell::symbol)
            .collect()
    }
}

mod the_detail_view {
    use crate::domain::errors::UnderstandingUnread;
    use crate::tests::infrastructure::detail_view::DetailScreen;
    use crate::tests::mothers::understanding_mother::UnderstandingMother;

    #[test]
    fn shows_exactly_the_three_events_of_the_slice_and_none_of_the_other() {
        let screen = DetailScreen::with_answer(Ok(UnderstandingMother::not_published()));

        assert_eq!(screen.matches("event-").count(), 3, "{screen}");
        assert!(!screen.contains("implement"), "{screen}");
    }

    #[test]
    fn shows_the_published_understanding() {
        let screen = DetailScreen::with_answer(Ok(UnderstandingMother::published()));

        assert!(screen.contains("El contador vive en Run"), "{screen}");
        assert!(screen.contains("Segunda linea tras un parrafo."), "{screen}");
    }

    #[test]
    fn says_that_no_understanding_is_published_instead_of_showing_an_error() {
        let screen = DetailScreen::with_answer(Ok(UnderstandingMother::not_published()));

        assert!(screen.contains("no understanding published"), "{screen}");
        assert!(!screen.contains("did not finish"), "{screen}");
    }

    #[test]
    fn shows_a_warning_with_the_reason_when_the_read_failed() {
        let screen = DetailScreen::with_answer(Err(UnderstandingUnread::CommandFailed {
            reason: "gh is not authenticated".to_string(),
        }));

        assert!(screen.contains("gh is not authenticated"), "{screen}");
        assert!(!screen.contains("no understanding published"), "{screen}");
    }
}
