mod the_split_screen {
    use ratatui::layout::Rect;

    use crate::domain::pane_size::PaneSize;
    use crate::infrastructure::split_screen::SplitScreen;

    #[test]
    fn gives_the_left_half_to_claude_and_the_right_half_to_the_board() {
        let (claude, board) = SplitScreen::areas(Rect::new(0, 0, 100, 30));

        assert_eq!(claude, Rect::new(0, 0, 50, 30));
        assert_eq!(board, Rect::new(50, 0, 50, 30));
    }

    #[test]
    fn the_pane_size_is_the_left_area_without_its_border() {
        assert_eq!(SplitScreen::pane_size(Rect::new(0, 0, 100, 30)), PaneSize::new(28, 48));
    }

    #[test]
    fn a_tiny_window_gives_a_pane_of_zero_and_never_underflows() {
        assert_eq!(SplitScreen::pane_size(Rect::new(0, 0, 1, 1)), PaneSize::new(0, 0));
    }
}

mod integration {
    use ratatui::layout::Rect;

    use crate::infrastructure::endless_pty_session::EndlessPtySession;
    use crate::infrastructure::split_screen::SplitScreen;
    use crate::tests::infrastructure::endless_follow_process::Waiting;
    use crate::tests::infrastructure::endless_pty_session::Launches;

    #[test]
    fn a_real_child_sees_exactly_the_rows_and_columns_the_split_gives_to_the_left_pane_and_after_a_resize() {
        let script = "stty size; read line; stty size; read line";
        let mut session = EndlessPtySession::spawn(
            &Launches::shell(script),
            SplitScreen::pane_size(Rect::new(0, 0, 100, 30)),
        )
        .unwrap();
        Waiting::until(|| Launches::text_of(&session).contains("28 48").then_some(()));

        session.resize(SplitScreen::pane_size(Rect::new(0, 0, 80, 20)));
        session.write(b"\n");

        Waiting::until(|| Launches::text_of(&session).contains("18 38").then_some(()));
    }
}
