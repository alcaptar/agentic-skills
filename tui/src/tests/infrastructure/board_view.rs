use ratatui::Terminal;
use ratatui::backend::TestBackend;

use crate::application::queries::watch_slices::WatchedBoard;
use crate::infrastructure::board_view::BoardView;

pub struct Screen;

impl Screen {
    pub fn text_of(watched: &WatchedBoard) -> String {
        let mut terminal = Terminal::new(TestBackend::new(100, 24)).unwrap();
        terminal.draw(|frame| BoardView::render(frame, watched)).unwrap();

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
