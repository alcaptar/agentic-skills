use ratatui::Terminal;
use ratatui::backend::TestBackend;
use ratatui::buffer::Buffer;
use ratatui::style::Color;

use crate::application::queries::read_slice_detail::SliceDetail;
use crate::application::queries::watch_slices::WatchedBoard;
use crate::domain::slice_key::SliceKey;
use crate::infrastructure::board_view::BoardView;
use crate::tests::mothers::screen_mother::ScreenMother;

pub struct Screen;

impl Screen {
    pub const WIDTH: u16 = 80;
    pub const HEIGHT: u16 = 24;

    pub fn text_of(watched: &WatchedBoard) -> String {
        Self::lines(&Self::painted(watched, None, None))
    }

    pub fn text_of_selecting(watched: &WatchedBoard, selected: &SliceKey, detail: Option<&SliceDetail>) -> String {
        Self::lines(&Self::painted(watched, Some(selected), detail))
    }

    pub fn painted(watched: &WatchedBoard, selected: Option<&SliceKey>, detail: Option<&SliceDetail>) -> Buffer {
        Self::painted_at(Self::WIDTH, watched, selected, detail)
    }

    pub fn painted_at(
        width: u16,
        watched: &WatchedBoard,
        selected: Option<&SliceKey>,
        detail: Option<&SliceDetail>,
    ) -> Buffer {
        let mut terminal = Terminal::new(TestBackend::new(width, Self::HEIGHT)).unwrap();
        terminal
            .draw(|frame| BoardView::render(frame, frame.area(), watched, selected, detail, ScreenMother::NOW))
            .unwrap();

        terminal.backend().buffer().clone()
    }

    pub fn lines(buffer: &Buffer) -> String {
        let mut text = String::new();
        for y in 0..buffer.area.height {
            for x in 0..buffer.area.width {
                text.push_str(buffer[(x, y)].symbol());
            }
            text.push('\n');
        }
        text
    }

    pub fn color_of(buffer: &Buffer, text: &str) -> Vec<Color> {
        let mut colors = Vec::new();
        for y in 0..buffer.area.height {
            let row: Vec<&str> = (0..buffer.area.width).map(|x| buffer[(x, y)].symbol()).collect();
            let joined: String = row.concat();
            if let Some(byte) = joined.find(text) {
                let column = joined[..byte].chars().count();
                colors.push(buffer[(u16::try_from(column).unwrap(), y)].fg);
            }
        }
        colors
    }
}

mod the_tray {
    use ratatui::style::Color;

    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::FixedProbe;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::mothers::screen_mother::ScreenMother;

    #[test]
    fn paints_the_agreed_screen_character_by_character() {
        let watched = Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive());

        let screen = Screen::text_of_selecting(&watched, &ScreenMother::key(1), None);

        assert_eq!(screen, include_str!("../screens/bandeja.txt"));
    }

    #[test]
    fn paints_each_glyph_with_its_colour_and_the_spend_near_the_budget_as_a_warning() {
        let watched = Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive());

        let buffer = Screen::painted(&watched, Some(&ScreenMother::key(1)), None);

        assert_eq!(Screen::color_of(&buffer, "◆"), vec![Color::Yellow]);
        assert_eq!(Screen::color_of(&buffer, "✕"), vec![Color::Red]);
        assert_eq!(Screen::color_of(&buffer, "◐"), vec![Color::Cyan, Color::Cyan]);
        assert_eq!(Screen::color_of(&buffer, "○"), vec![Color::DarkGray]);
        assert_eq!(Screen::color_of(&buffer, "✓"), vec![Color::Green]);
        assert_eq!(Screen::color_of(&buffer, "$42/50"), vec![Color::Yellow]);
    }

    #[test]
    fn shows_the_spend_from_eighty_percent_of_the_budget_and_not_below() {
        let at_the_edge = Watching::one_tick(Watching::lines(vec![ScreenMother::spending(40.0)]));
        let below = Watching::one_tick(Watching::lines(vec![ScreenMother::spending(39.99)]));

        assert!(Screen::text_of(&at_the_edge).contains("$40/50"));
        assert!(!Screen::text_of(&below).contains("$40/50"));
    }

    #[test]
    fn paints_the_last_action_under_a_running_slice_and_a_dead_process_among_what_needs_you() {
        let watched = Watching::entries(
            ScreenMother::feature_with_activity(),
            FixedProbe::alive_only(&[ScreenMother::JUDGED_PID]),
        );

        let buffer = Screen::painted(&watched, Some(&ScreenMother::key(1)), None);

        assert_eq!(
            Screen::lines(&buffer),
            include_str!("../screens/bandeja-con-actividad.txt")
        );
        assert_eq!(Screen::color_of(&buffer, "proceso muerto"), vec![Color::Red]);
    }
}

mod the_tray_with_trouble {
    use crate::domain::errors::FollowLineRejected;
    use crate::tests::application::watching::Watching;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;

    #[test]
    fn paints_a_rejection_and_keeps_the_slices_on_screen() {
        let watched = Watching::one_tick(vec![
            Watching::lines(vec![FollowLineMother::child_of(140, 150)]).remove(0),
            Err(FollowLineRejected::UnsupportedVersion { version: 1 }),
        ]);

        let screen = Screen::text_of(&watched);

        assert!(screen.contains("unsupported follow line version 1"), "{screen}");
        assert!(screen.contains(FollowLineMother::NAME), "{screen}");
    }

    #[test]
    fn paints_nothing_about_errors_when_every_line_was_valid() {
        let watched = Watching::one_tick(Watching::lines(vec![FollowLineMother::orphan(170)]));

        assert!(!Screen::text_of(&watched).contains("unsupported"));
    }

    #[test]
    fn names_a_feature_without_parent_and_marks_only_the_selected_slice() {
        let watched = Watching::three_slices_in_two_groups();

        let screen = Screen::text_of_selecting(&watched, &Watching::key(160), None);

        assert!(screen.contains("alcaptar/agentic-skills sin padre"), "{screen}");
        assert_eq!(screen.matches('>').count(), 1, "{screen}");
    }
}

mod the_tray_with_an_open_detail {
    use crate::application::queries::read_slice_detail::ReadSliceDetail;
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::FixedProbe;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::mothers::screen_mother::ScreenMother;

    #[test]
    fn paints_the_detail_over_the_whole_board() {
        let watched = Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive());
        let detail = ReadSliceDetail::execute(ScreenMother::key(4));

        let screen = Screen::text_of_selecting(&watched, &ScreenMother::key(4), Some(&detail));

        assert_eq!(screen, include_str!("../screens/detalle-bloqueada.txt"));
    }

    #[test]
    fn a_detail_for_a_slice_that_is_no_longer_on_the_board_paints_only_the_board() {
        let watched = Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive());
        let detail = ReadSliceDetail::execute(Watching::key(999));

        let screen = Screen::text_of_selecting(&watched, &ScreenMother::key(1), Some(&detail));

        assert_eq!(screen, include_str!("../screens/bandeja.txt"));
    }
}

mod the_tray_with_several_features {
    use crate::domain::errors::FollowLineRejected;
    use crate::tests::application::watching::Watching;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;

    #[test]
    fn keeps_the_keys_and_the_rejection_on_screen_when_the_groups_fill_it() {
        let mut deliveries = Watching::lines(
            (0..12)
                .map(|issue| FollowLineMother::child_of(140 + issue, 150 + issue))
                .collect(),
        );
        deliveries.push(Err(FollowLineRejected::UnsupportedVersion { version: 3 }));
        let watched = Watching::one_tick(deliveries);

        let screen = Screen::text_of(&watched);

        assert!(screen.contains("unsupported follow line version 3"), "{screen}");
        assert!(screen.contains("enter detalle"), "{screen}");
    }
}

mod the_tray_at_the_width_of_half_a_laptop_screen {
    use crate::application::queries::read_slice_detail::ReadSliceDetail;
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::FixedProbe;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::mothers::screen_mother::ScreenMother;

    const NARROW: u16 = 58;

    #[test]
    fn keeps_every_summary_whole_by_shortening_the_names() {
        let watched = Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive());

        let screen = Screen::lines(&Screen::painted_at(NARROW, &watched, Some(&ScreenMother::key(1)), None));

        assert_eq!(screen, include_str!("../screens/bandeja-58.txt"));
    }

    #[test]
    fn breaks_the_command_to_reopen_and_keeps_each_duration_on_its_line() {
        let watched = Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive());
        let detail = ReadSliceDetail::execute(ScreenMother::key(4));

        let screen = Screen::lines(&Screen::painted_at(
            NARROW,
            &watched,
            Some(&ScreenMother::key(4)),
            Some(&detail),
        ));

        assert_eq!(screen, include_str!("../screens/detalle-bloqueada-58.txt"));
    }
}
