use ratatui::Terminal;
use ratatui::backend::TestBackend;

use crate::application::queries::read_slice_detail::SliceDetail;
use crate::application::queries::watch_slices::WatchedBoard;
use crate::domain::slice_key::SliceKey;
use crate::infrastructure::board_view::BoardView;

pub struct Screen;

impl Screen {
    pub fn text_of(watched: &WatchedBoard) -> String {
        Self::painted(watched, None, None)
    }

    pub fn text_of_selecting(watched: &WatchedBoard, selected: &SliceKey, detail: Option<&SliceDetail>) -> String {
        Self::painted(watched, Some(selected), detail)
    }

    fn painted(watched: &WatchedBoard, selected: Option<&SliceKey>, detail: Option<&SliceDetail>) -> String {
        let mut terminal = Terminal::new(TestBackend::new(100, 24)).unwrap();
        terminal
            .draw(|frame| BoardView::render(frame, watched, selected, detail))
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

mod the_board_view {
    use crate::domain::errors::FollowLineRejected;
    use crate::tests::application::watching::Watching;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;

    #[test]
    fn paints_each_group_with_its_slices_name_step_and_status() {
        let watched = Watching::one_tick(Watching::lines(vec![
            FollowLineMother::child_of(140, 150),
            FollowLineMother::orphan(170),
        ]));

        let screen = Screen::text_of(&watched);

        assert!(screen.contains("alcaptar/agentic-skills #140"), "{screen}");
        assert!(screen.contains("alcaptar/agentic-skills no parent"), "{screen}");
        assert!(screen.contains(FollowLineMother::NAME), "{screen}");
        assert!(screen.contains("slice-02"), "{screen}");
        assert!(screen.contains("run-controls"), "{screen}");
        assert!(screen.contains("advancing"), "{screen}");
    }

    #[test]
    fn paints_a_rejection_and_keeps_the_slices_on_screen() {
        let watched = Watching::one_tick(vec![
            Ok(FollowLineMother::child_of(140, 150)),
            Err(FollowLineRejected::WrongValue {
                key: "issue".to_string(),
                reason: "expected a number".to_string(),
            }),
        ]);

        let screen = Screen::text_of(&watched);

        assert!(
            screen.contains("wrong value for `issue`: expected a number"),
            "{screen}"
        );
        assert!(screen.contains(FollowLineMother::NAME), "{screen}");
    }

    #[test]
    fn paints_nothing_about_errors_when_every_line_was_valid() {
        let watched = Watching::one_tick(Watching::lines(vec![FollowLineMother::orphan(170)]));

        assert!(!Screen::text_of(&watched).contains("wrong value"));
    }
}

mod the_board_view_with_a_selection {
    use crate::application::queries::read_slice_detail::ReadSliceDetail;
    use crate::domain::errors::UnderstandingUnread;
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::ScriptedUnderstandingSource;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;
    use crate::tests::mothers::understanding_mother::UnderstandingMother;

    #[test]
    fn marks_only_the_selected_slice() {
        let watched = Watching::three_slices_in_two_groups();

        let screen = Screen::text_of_selecting(&watched, &Watching::key(160), None);

        assert_eq!(screen.matches("> ").count(), 1, "{screen}");
    }

    #[test]
    fn paints_the_understanding_of_the_open_detail_next_to_the_board() {
        let watched = Watching::three_slices_in_two_groups();
        let (source, _) = ScriptedUnderstandingSource::answering(Ok(UnderstandingMother::published()));
        let detail = ReadSliceDetail::new(source).execute(Watching::key(160));

        let screen = Screen::text_of_selecting(&watched, &Watching::key(160), Some(&detail));

        assert!(screen.contains("El contador vive en Run"), "{screen}");
        assert!(screen.contains("alcaptar/agentic-skills #140"), "{screen}");
    }

    #[test]
    fn a_read_that_ran_out_of_time_shows_a_warning_and_keeps_the_board_on_screen() {
        let watched = Watching::one_tick(Watching::lines(vec![FollowLineMother::child_of(140, 150)]));
        let timed_out = UnderstandingUnread::TimedOut {
            budget: std::time::Duration::from_millis(100),
        };
        let (source, _) = ScriptedUnderstandingSource::answering(Err(timed_out));
        let detail = ReadSliceDetail::new(source).execute(Watching::key(150));

        let screen = Screen::text_of_selecting(&watched, &Watching::key(150), Some(&detail));

        assert!(screen.contains("did not finish within 100ms"), "{screen}");
        assert!(screen.contains(FollowLineMother::NAME), "{screen}");
        assert!(screen.contains("alcaptar/agentic-skills #140"), "{screen}");
    }

    #[test]
    fn a_detail_for_a_slice_that_is_no_longer_on_the_board_paints_only_the_board() {
        let watched = Watching::one_tick(Watching::lines(vec![FollowLineMother::child_of(140, 150)]));
        let (source, _) = ScriptedUnderstandingSource::answering(Ok(UnderstandingMother::published()));
        let detail = ReadSliceDetail::new(source).execute(Watching::key(999));

        let screen = Screen::text_of_selecting(&watched, &Watching::key(150), Some(&detail));

        assert!(!screen.contains("El contador vive en Run"), "{screen}");
    }
}
