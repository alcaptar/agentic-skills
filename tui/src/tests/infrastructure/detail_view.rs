use ratatui::Terminal;
use ratatui::backend::TestBackend;

use crate::domain::slice_row::SliceRow;
use crate::infrastructure::detail_view::DetailView;
use crate::tests::infrastructure::board_view::Screen;
use crate::tests::mothers::screen_mother::ScreenMother;

pub struct DetailScreen;

impl DetailScreen {
    pub fn text_of(row: &SliceRow) -> String {
        let mut terminal = Terminal::new(TestBackend::new(Screen::WIDTH, Screen::HEIGHT)).unwrap();
        terminal
            .draw(|frame| DetailView::render(frame, frame.area(), row, ScreenMother::NOW))
            .unwrap();

        Screen::lines(terminal.backend().buffer())
    }
}

mod the_detail_view {
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::FixedProbe;
    use crate::tests::infrastructure::detail_view::DetailScreen;
    use crate::tests::mothers::screen_mother::ScreenMother;

    #[test]
    fn of_a_running_slice_shows_what_the_judge_is_doing_and_its_history_character_by_character() {
        let watched = Watching::entries(
            ScreenMother::feature_with_activity(),
            FixedProbe::alive_only(&[ScreenMother::JUDGED_PID, ScreenMother::IMPLEMENTED_PID]),
        );
        let row = watched.board().row(&ScreenMother::key(2)).unwrap();

        assert_eq!(
            DetailScreen::text_of(row),
            include_str!("../screens/detalle-en-curso.txt")
        );
    }

    #[test]
    fn of_a_slice_with_a_round_without_changes_says_so_in_its_history() {
        let watched = Watching::one_tick(Watching::lines(ScreenMother::a_round_without_changes()));
        let row = watched.board().row(&ScreenMother::key(7)).unwrap();

        let screen = DetailScreen::text_of(row);

        assert!(screen.contains("implementa, vuelta 1, sin cambios"), "{screen}");
        assert!(screen.contains("implementa, vuelta 1     "), "{screen}");
    }

    #[test]
    fn of_a_running_slice_does_not_offer_to_reopen_it() {
        let watched = Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive());
        let row = watched.board().row(&ScreenMother::key(2)).unwrap();

        assert!(!DetailScreen::text_of(row).contains("slice-runner retry"));
    }
}

mod the_detail_view_of_a_long_story {
    use crate::tests::application::watching::Watching;
    use crate::tests::infrastructure::detail_view::DetailScreen;
    use crate::tests::mothers::screen_mother::ScreenMother;

    #[test]
    fn keeps_the_command_to_reopen_and_drops_the_oldest_steps() {
        let watched = Watching::one_tick(Watching::lines(ScreenMother::a_long_blocked_story()));
        let row = watched.board().row(&ScreenMother::key(8)).unwrap();

        let screen = DetailScreen::text_of(row);

        assert!(screen.contains("slice-runner retry 533"), "{screen}");
        assert!(screen.contains("bloqueada: controles"), "{screen}");
        assert!(!screen.contains("hace 40m"), "{screen}");
    }
}
