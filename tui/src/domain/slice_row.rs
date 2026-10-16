use crate::domain::activity_line::ActivityLine;
use crate::domain::attention::Attention;
use crate::domain::closure::Closure;
use crate::domain::follow_line::FollowLine;
use crate::domain::liveness::Liveness;
use crate::domain::parent::Parent;
use crate::domain::slice_key::SliceKey;
use crate::domain::slice_subject::SliceSubject;
use crate::domain::transition::Transition;

#[derive(Debug, Clone, PartialEq)]
pub struct SliceRow {
    key: SliceKey,
    subject: SliceSubject,
    transitions: Vec<Transition>,
    activity: Vec<ActivityLine>,
    liveness: Liveness,
}

impl SliceRow {
    const KEPT_ACTIVITY: usize = 50;

    pub fn first(line: FollowLine) -> Self {
        let key = SliceKey::of(&line);
        let (subject, transition) = line.into_parts();

        Self {
            key,
            subject,
            transitions: vec![transition],
            activity: Vec::new(),
            liveness: Liveness::Unchecked,
        }
    }

    pub fn with_line(&self, line: FollowLine) -> Self {
        let (subject, transition) = line.into_parts();
        let mut transitions = self.transitions.clone();
        if !transitions.last().is_some_and(|last| transition.repeats(last)) {
            transitions.push(transition);
        }

        Self {
            subject: subject.known_over(&self.subject),
            transitions,
            ..self.clone()
        }
    }

    pub fn with_activity(&self, line: ActivityLine) -> Self {
        let mut activity = self.activity.clone();
        activity.push(line);
        let surplus = activity.len().saturating_sub(Self::KEPT_ACTIVITY);
        activity.drain(..surplus);

        Self {
            activity,
            ..self.clone()
        }
    }

    pub fn with_liveness(&self, liveness: Liveness) -> Self {
        Self {
            liveness,
            ..self.clone()
        }
    }

    pub fn is_the_slice_of(&self, line: &FollowLine) -> bool {
        self.key == SliceKey::of(line)
    }

    pub fn key(&self) -> &SliceKey {
        &self.key
    }

    pub fn subject(&self) -> &SliceSubject {
        &self.subject
    }

    pub fn transitions(&self) -> &[Transition] {
        &self.transitions
    }

    pub fn activity(&self) -> &[ActivityLine] {
        &self.activity
    }

    pub fn latest(&self) -> &Transition {
        let index = self.transitions.len().saturating_sub(1);

        &self.transitions[index]
    }

    pub fn repo(&self) -> &str {
        self.subject.repo()
    }

    pub fn parent(&self) -> Parent {
        self.subject.parent()
    }

    pub fn label(&self) -> &str {
        self.subject.name().unwrap_or_else(|| self.subject.slice_id())
    }

    pub fn pid(&self) -> Option<u32> {
        self.transitions.iter().rev().find_map(Transition::pid)
    }

    pub fn pull_request(&self) -> Option<u64> {
        self.transitions.iter().rev().find_map(Transition::pull_request)
    }

    pub fn is_running(&self) -> bool {
        self.latest().closure() == Closure::InProgress
    }

    pub fn process_is_gone(&self) -> bool {
        self.is_running() && self.liveness == Liveness::Gone
    }

    pub fn attention(&self) -> Attention {
        match self.latest().closure() {
            Closure::Pending => Attention::Pending,
            Closure::InProgress if self.process_is_gone() => Attention::NeedsYou,
            Closure::InProgress => Attention::Running,
            Closure::AwaitingMerge | Closure::Blocked(_) | Closure::Aborted(_) => Attention::NeedsYou,
            Closure::Merged => Attention::Finished,
        }
    }
}
