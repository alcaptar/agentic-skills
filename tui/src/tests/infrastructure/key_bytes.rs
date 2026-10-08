use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};
use vt100::Parser;

pub struct ChildScreens;

impl ChildScreens {
    pub fn plain() -> Parser {
        Parser::new(24, 80, 0)
    }

    pub fn with_application_cursor() -> Parser {
        Self::after(b"\x1b[?1h")
    }

    pub fn with_bracketed_paste() -> Parser {
        Self::after(b"\x1b[?2004h")
    }

    fn after(sequence: &[u8]) -> Parser {
        let mut parser = Self::plain();
        parser.process(sequence);

        parser
    }

    pub fn press(code: KeyCode) -> KeyEvent {
        KeyEvent::new(code, KeyModifiers::NONE)
    }

    pub fn press_with_control(character: char) -> KeyEvent {
        KeyEvent::new(KeyCode::Char(character), KeyModifiers::CONTROL)
    }
}

mod the_bytes_of_a_key {
    use crossterm::event::KeyCode;

    use crate::infrastructure::key_bytes::KeyBytes;
    use crate::tests::infrastructure::key_bytes::ChildScreens;

    #[test]
    fn escape_control_c_and_enter_are_their_single_bytes() {
        let parser = ChildScreens::plain();
        let screen = parser.screen();

        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Esc), screen), b"\x1b");
        assert_eq!(KeyBytes::of(ChildScreens::press_with_control('c'), screen), b"\x03");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Enter), screen), b"\r");
    }

    #[test]
    fn the_arrows_use_the_csi_form_in_normal_mode() {
        let parser = ChildScreens::plain();
        let screen = parser.screen();

        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Up), screen), b"\x1b[A");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Down), screen), b"\x1b[B");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Right), screen), b"\x1b[C");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Left), screen), b"\x1b[D");
    }

    #[test]
    fn the_arrows_use_the_ss3_form_once_the_child_asks_for_application_cursor_mode() {
        let parser = ChildScreens::with_application_cursor();
        let screen = parser.screen();

        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Up), screen), b"\x1bOA");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Down), screen), b"\x1bOB");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Right), screen), b"\x1bOC");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Left), screen), b"\x1bOD");
    }

    #[test]
    fn a_character_is_its_utf8_bytes() {
        let parser = ChildScreens::plain();

        assert_eq!(
            KeyBytes::of(ChildScreens::press(KeyCode::Char('ñ')), parser.screen()),
            "ñ".as_bytes()
        );
    }

    #[test]
    fn a_key_with_no_translation_gives_no_bytes() {
        let parser = ChildScreens::plain();

        assert!(KeyBytes::of(ChildScreens::press(KeyCode::F(5)), parser.screen()).is_empty());
    }
}

mod the_bytes_of_a_paste {
    use crate::infrastructure::key_bytes::KeyBytes;
    use crate::tests::infrastructure::key_bytes::ChildScreens;

    #[test]
    fn are_wrapped_in_the_paste_markers_when_the_child_enabled_bracketed_paste() {
        let parser = ChildScreens::with_bracketed_paste();

        assert_eq!(KeyBytes::of_paste("a\nb", parser.screen()), b"\x1b[200~a\nb\x1b[201~");
    }

    #[test]
    fn are_typed_with_carriage_returns_when_the_child_did_not_enable_it() {
        let parser = ChildScreens::plain();

        assert_eq!(KeyBytes::of_paste("a\nb", parser.screen()), b"a\rb");
    }
}
