#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ClosingReason {
    Controls,
    Judge,
    CiRed,
    CiIndeterminate,
    CiConflict,
    Worktree,
    Budget,
    UnmeasuredCall,
}

impl ClosingReason {
    pub fn parse(text: &str) -> Option<Self> {
        match text {
            "controls" => Some(Self::Controls),
            "judge" => Some(Self::Judge),
            "ci-red" => Some(Self::CiRed),
            "ci-indeterminate" => Some(Self::CiIndeterminate),
            "ci-conflict" => Some(Self::CiConflict),
            "worktree" => Some(Self::Worktree),
            "budget" => Some(Self::Budget),
            "unmeasured-call" => Some(Self::UnmeasuredCall),
            _ => None,
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            Self::Controls => "controles",
            Self::Judge => "juez",
            Self::CiRed => "ci roja",
            Self::CiIndeterminate => "ci indeterminada",
            Self::CiConflict => "conflicto",
            Self::Worktree => "worktree",
            Self::Budget => "presupuesto",
            Self::UnmeasuredCall => "llamada no medida",
        }
    }

    pub fn blocks(self) -> bool {
        match self {
            Self::Controls | Self::Judge | Self::CiRed | Self::CiIndeterminate | Self::CiConflict | Self::Worktree => {
                true
            }
            Self::Budget | Self::UnmeasuredCall => false,
        }
    }
}
