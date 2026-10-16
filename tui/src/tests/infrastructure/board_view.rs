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
            .draw(|frame| BoardView::render(frame, frame.area(), watched, selected, detail))
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
    use crate::tests::application::watching::Watching;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;

    #[test]
    fn marks_only_the_selected_slice() {
        let watched = Watching::three_slices_in_two_groups();

        let screen = Screen::text_of_selecting(&watched, &Watching::key(160), None);

        assert_eq!(screen.matches("> ").count(), 1, "{screen}");
    }

    #[test]
    fn paints_the_open_detail_next_to_the_board() {
        let first = FollowLineMother::child_of(141, 160);
        let watched = Watching::one_tick(Watching::lines(vec![
            first.clone(),
            FollowLineMother::moved_to(&first, "event-1"),
            FollowLineMother::moved_to(&first, "event-2"),
        ]));
        let detail = ReadSliceDetail::execute(Watching::key(160));

        let screen = Screen::text_of_selecting(&watched, &Watching::key(160), Some(&detail));

        assert!(screen.contains("event-1"), "{screen}");
        assert!(screen.contains("alcaptar/agentic-skills #141"), "{screen}");
    }

    #[test]
    fn a_detail_for_a_slice_that_is_no_longer_on_the_board_paints_only_the_board() {
        let first = FollowLineMother::child_of(140, 150);
        let watched = Watching::one_tick(Watching::lines(vec![
            first.clone(),
            FollowLineMother::moved_to(&first, "event-1"),
            FollowLineMother::moved_to(&first, "event-2"),
        ]));
        let detail = ReadSliceDetail::execute(Watching::key(999));

        let screen = Screen::text_of_selecting(&watched, &Watching::key(150), Some(&detail));

        assert!(!screen.contains("event-1"), "{screen}");
    }
}

mod the_board_view_with_version_2_lines {
    use crate::infrastructure::follow_line_payload::FollowLinePayload;
    use crate::tests::application::watching::Watching;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::infrastructure::follow_line_payload::RawTransition;

    struct Feed;

    impl Feed {
        fn watched_from(raws: &[String]) -> crate::application::queries::watch_slices::WatchedBoard {
            Watching::one_tick(raws.iter().filter_map(|raw| FollowLinePayload::delivery(raw)).collect())
        }
    }

    #[test]
    fn paints_a_blocked_slice_with_its_reason() {
        let screen = Screen::text_of(&Feed::watched_from(&[RawTransition::blocked_by_controls()]));

        assert!(screen.contains("bloqueada: controles"), "{screen}");
    }

    #[test]
    fn paints_a_slice_waiting_for_the_merge() {
        let screen = Screen::text_of(&Feed::watched_from(&[RawTransition::awaiting_merge()]));

        assert!(screen.contains("esperando merge"), "{screen}");
    }

    #[test]
    fn paints_an_error_naming_a_version_it_does_not_understand() {
        let screen = Screen::text_of(&Feed::watched_from(&[
            RawTransition::awaiting_merge(),
            r#"{"version":3,"kind":"transition"}"#.to_string(),
        ]));

        assert!(screen.contains("version 3"), "{screen}");
        assert!(screen.contains("esperando merge"), "{screen}");
    }

    #[test]
    fn paints_an_error_naming_a_kind_it_does_not_understand() {
        let screen = Screen::text_of(&Feed::watched_from(
            &[r#"{"version":2,"kind":"heartbeat"}"#.to_string()],
        ));

        assert!(screen.contains("heartbeat"), "{screen}");
    }

    #[test]
    fn an_activity_line_changes_no_row_and_leaves_no_error() {
        let watched = Feed::watched_from(&[RawTransition::awaiting_merge(), RawTransition::activity()]);
        let alone = Feed::watched_from(&[RawTransition::awaiting_merge()]);

        assert_eq!(watched, alone);
        assert_eq!(watched.rejection(), None);
    }
}
