use crossterm::event::{KeyCode, KeyEvent, KeyEventKind, KeyModifiers};
use vt100::Screen;

use crate::infrastructure::key_bytes::KeyBytes;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Order {
    Quit,
    Previous,
    Next,
    Open,
    Close,
    Nothing,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Focus {
    Claude,
    Board,
}

impl Focus {
    pub fn toggled(self) -> Self {
        match self {
            Self::Claude => Self::Board,
            Self::Board => Self::Claude,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Routed {
    ToClaude(Vec<u8>),
    Board(Order),
    ToggleFocus,
    Ignored,
}

pub struct KeyRouting;

impl KeyRouting {
    const CONTROL_BACKSLASH: KeyCode = KeyCode::Char('4');
    const BINDINGS: [(KeyCode, Order); 7] = [
        (KeyCode::Char('q'), Order::Quit),
        (KeyCode::Up, Order::Previous),
        (KeyCode::Char('k'), Order::Previous),
        (KeyCode::Down, Order::Next),
        (KeyCode::Char('j'), Order::Next),
        (KeyCode::Enter, Order::Open),
        (KeyCode::Esc, Order::Close),
    ];

    pub fn route(focus: Focus, key: KeyEvent, screen: &Screen) -> Routed {
        if key.kind != KeyEventKind::Press {
            return Routed::Ignored;
        }
        if key.code == Self::CONTROL_BACKSLASH && key.modifiers.contains(KeyModifiers::CONTROL) {
            return Routed::ToggleFocus;
        }

        match focus {
            Focus::Claude => Routed::ToClaude(KeyBytes::of(key, screen)),
            Focus::Board => Routed::Board(Self::order_of(key)),
        }
    }

    fn order_of(key: KeyEvent) -> Order {
        if key.code == KeyCode::Char('c') && key.modifiers.contains(KeyModifiers::CONTROL) {
            return Order::Quit;
        }

        Self::BINDINGS
            .iter()
            .find(|(code, _)| *code == key.code)
            .map_or(Order::Nothing, |(_, order)| *order)
    }
}
