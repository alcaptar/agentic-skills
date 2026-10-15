use ratatui::Terminal;
use ratatui::backend::TestBackend;

use crate::domain::follow_line::FollowLine;
use crate::domain::slice_row::SliceRow;
use crate::infrastructure::detail_view::DetailView;
use crate::tests::application::watching::Watching;
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

    pub fn of_the_slice() -> String {
        let watched = Watching::one_tick(Watching::lines(Self::lines_of_one_slice_and_one_of_another()));
        let row = watched.board().row(&Watching::key(150)).unwrap();

        Self::text_of(row)
    }

    pub fn text_of(row: &SliceRow) -> String {
        let mut terminal = Terminal::new(TestBackend::new(100, 24)).unwrap();
        terminal
            .draw(|frame| DetailView::render(frame, frame.area(), row))
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
    use crate::tests::infrastructure::detail_view::DetailScreen;

    #[test]
    fn shows_exactly_the_three_events_of_the_slice_and_none_of_the_other() {
        let screen = DetailScreen::of_the_slice();

        assert_eq!(screen.matches("event-").count(), 3, "{screen}");
        assert!(!screen.contains("implement"), "{screen}");
    }
}
