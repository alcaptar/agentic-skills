use ratatui::Terminal;
use ratatui::backend::TestBackend;
use ratatui::buffer::Buffer;
use ratatui::layout::Rect;

use crate::infrastructure::claude_pane::ClaudePane;
use crate::infrastructure::endless_pty_session::EndlessPtySession;

pub struct PaneScreen;

impl PaneScreen {
    pub fn painted(session: &mut EndlessPtySession, focused: bool) -> Buffer {
        let mut terminal = Terminal::new(TestBackend::new(40, 10)).unwrap();
        terminal
            .draw(|frame| ClaudePane::render(frame, Rect::new(0, 0, 40, 10), session, focused))
            .unwrap();

        terminal.backend().buffer().clone()
    }

    pub fn text_of(buffer: &Buffer) -> String {
        buffer.content().iter().map(ratatui::buffer::Cell::symbol).collect()
    }
}

mod integration {
    use ratatui::style::Color;

    use crate::infrastructure::endless_pty_session::EndlessPtySession;
    use crate::tests::infrastructure::claude_pane::PaneScreen;
    use crate::tests::infrastructure::endless_follow_process::Waiting;
    use crate::tests::infrastructure::endless_pty_session::Launches;

    #[test]
    fn says_the_session_ended_once_claude_finishes_and_keeps_what_it_printed() {
        let mut session = EndlessPtySession::spawn(&Launches::shell("echo farewell"), Launches::size()).unwrap();
        Waiting::until(|| session.has_ended().then_some(()));
        Waiting::until(|| Launches::text_of(&session).contains("farewell").then_some(()));

        let text = PaneScreen::text_of(&PaneScreen::painted(&mut session, true));

        assert!(text.contains("claude session ended"), "{text}");
        assert!(text.contains("farewell"), "{text}");
    }

    #[test]
    fn does_not_say_it_while_the_session_is_alive() {
        let mut session = EndlessPtySession::spawn(&Launches::shell("echo hello; sleep 60"), Launches::size()).unwrap();
        Waiting::until(|| Launches::text_of(&session).contains("hello").then_some(()));

        let text = PaneScreen::text_of(&PaneScreen::painted(&mut session, true));

        assert!(text.contains("hello"), "{text}");
        assert!(!text.contains("claude session ended"), "{text}");
    }

    #[test]
    fn highlights_the_border_only_when_it_has_the_focus() {
        let mut session = EndlessPtySession::spawn(&Launches::shell("sleep 60"), Launches::size()).unwrap();

        let focused = PaneScreen::painted(&mut session, true);
        let unfocused = PaneScreen::painted(&mut session, false);

        assert_eq!(focused[(0, 0)].fg, Color::Cyan);
        assert_ne!(unfocused[(0, 0)].fg, Color::Cyan);
    }
}
