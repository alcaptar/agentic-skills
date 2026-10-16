pub struct RawLine;

impl RawLine {
    pub fn with(issue: &str, extra: &str) -> String {
        format!(
            r#"{{"version":1,"repo":"alcaptar/agentic-skills","issue":{issue},"slice_id":"slice-05","step":"run-controls","status":"advancing"{extra}}}"#
        )
    }

    pub fn valid() -> String {
        Self::with("150", "")
    }
}

mod an_unknown_key {
    use crate::infrastructure::follow_line_payload::FollowLinePayload;
    use crate::tests::infrastructure::follow_line_payload::RawLine;

    #[test]
    fn is_ignored() {
        let raw = RawLine::with("150", r#","something_new":{"nested":true}"#);

        let line = FollowLinePayload::parsed(&raw).unwrap();

        assert_eq!(line.issue(), 150);
        assert_eq!(line.slice_id(), "slice-05");
    }
}

mod a_known_key_with_a_wrong_value {
    use crate::domain::errors::FollowLineRejected;
    use crate::infrastructure::follow_line_payload::FollowLinePayload;
    use crate::tests::infrastructure::follow_line_payload::RawLine;

    #[test]
    fn is_a_typed_rejection_naming_the_key() {
        let rejected = FollowLinePayload::parsed(&RawLine::with(r#""one hundred""#, "")).unwrap_err();

        assert!(
            matches!(rejected, FollowLineRejected::WrongValue { ref key, .. } if key == "issue"),
            "{rejected:?}"
        );
    }

    #[test]
    fn also_rejects_an_optional_key_that_arrives_with_the_wrong_type() {
        let rejected = FollowLinePayload::parsed(&RawLine::with("150", r#","parent":"140""#)).unwrap_err();

        assert!(
            matches!(rejected, FollowLineRejected::WrongValue { ref key, .. } if key == "parent"),
            "{rejected:?}"
        );
    }

    #[test]
    fn also_rejects_a_missing_required_key() {
        let raw = r#"{"repo":"alcaptar/agentic-skills","issue":150,"slice_id":"slice-05","step":"run-controls"}"#;

        let rejected = FollowLinePayload::parsed(raw).unwrap_err();

        assert!(
            matches!(rejected, FollowLineRejected::WrongValue { ref key, .. } if key == "status"),
            "{rejected:?}"
        );
    }
}

mod a_line_that_is_not_a_json_object {
    use crate::domain::errors::FollowLineRejected;
    use crate::infrastructure::follow_line_payload::FollowLinePayload;

    #[test]
    fn is_rejected_with_the_text_it_carried() {
        assert_eq!(
            FollowLinePayload::parsed("Traceback (most recent call last)").unwrap_err(),
            FollowLineRejected::NotJson {
                line: "Traceback (most recent call last)".to_string()
            }
        );
        assert_eq!(
            FollowLinePayload::parsed("[1, 2]").unwrap_err(),
            FollowLineRejected::NotJson {
                line: "[1, 2]".to_string()
            }
        );
    }
}

mod the_optional_keys {
    use crate::domain::parent::Parent;
    use crate::infrastructure::follow_line_payload::FollowLinePayload;
    use crate::tests::infrastructure::follow_line_payload::RawLine;

    #[test]
    fn become_an_absent_parent_and_no_name_when_left_out() {
        let line = FollowLinePayload::parsed(&RawLine::valid()).unwrap();

        assert_eq!(line.parent(), Parent::Absent);
        assert_eq!(line.name(), None);
    }

    #[test]
    fn carry_the_parent_and_the_name_when_present() {
        let line =
            FollowLinePayload::parsed(&RawLine::with("150", r#","parent":140,"name":"follow-speaks-json""#)).unwrap();

        assert_eq!(line.parent(), Parent::Issue(140));
        assert_eq!(line.name(), Some("follow-speaks-json"));
    }
}

pub struct RawTransition;

impl RawTransition {
    pub fn with(standing_and_more: &str) -> String {
        format!(
            r#"{{"version":2,"kind":"transition","ts":1767268800000,"repo":"alcaptar/agentic-skills","issue":150,"slice_id":"slice-05",{standing_and_more}}}"#
        )
    }

    pub fn blocked_by_controls() -> String {
        Self::with(r#""standing":"blocked","reason":"controls","step":"run-controls""#)
    }

    pub fn awaiting_merge() -> String {
        Self::with(r#""standing":"awaiting-merge","step":"await-merge","pull_request":151"#)
    }

    pub fn activity() -> String {
        r#"{"version":2,"kind":"activity","ts":1767268920000,"repo":"alcaptar/agentic-skills","issue":150,"slice_id":"slice-05","actor":"implementer","tool":"Edit","target":"a.py"}"#.to_string()
    }
}

mod a_version_2_transition {
    use crate::domain::errors::FollowLineRejected;
    use crate::domain::parent::Parent;
    use crate::infrastructure::follow_line_payload::FollowLinePayload;
    use crate::tests::infrastructure::follow_line_payload::RawTransition;

    #[test]
    fn blocked_by_controls_carries_its_step_and_the_label_of_github() {
        let line = FollowLinePayload::parsed(&RawTransition::blocked_by_controls()).unwrap();

        assert_eq!(line.status(), "bloqueada: controles");
        assert_eq!(line.step(), "run-controls");
        assert_eq!(line.slice_id(), "slice-05");
        assert_eq!(line.parent(), Parent::Absent);
    }

    #[test]
    fn awaiting_merge_is_labelled_as_such() {
        let line = FollowLinePayload::parsed(&RawTransition::awaiting_merge()).unwrap();

        assert_eq!(line.status(), "esperando merge");
    }

    #[test]
    fn a_pending_one_has_no_step() {
        let line = FollowLinePayload::parsed(&RawTransition::with(r#""standing":"pending""#)).unwrap();

        assert_eq!(line.status(), "pendiente");
        assert_eq!(line.step(), "");
    }

    #[test]
    fn a_blocked_one_without_reason_is_rejected_naming_the_reason() {
        let rejected =
            FollowLinePayload::parsed(&RawTransition::with(r#""standing":"blocked","step":"verify""#)).unwrap_err();

        assert!(
            matches!(rejected, FollowLineRejected::WrongValue { ref key, .. } if key == "reason"),
            "{rejected:?}"
        );
    }

    #[test]
    fn an_unknown_standing_is_rejected_naming_the_standing() {
        let rejected = FollowLinePayload::parsed(&RawTransition::with(r#""standing":"sleeping""#)).unwrap_err();

        assert!(
            matches!(rejected, FollowLineRejected::WrongValue { ref key, .. } if key == "standing"),
            "{rejected:?}"
        );
    }
}

mod a_line_of_a_version_the_interface_does_not_speak {
    use crate::domain::errors::FollowLineRejected;
    use crate::infrastructure::follow_line_payload::FollowLinePayload;

    #[test]
    fn is_rejected_naming_the_version() {
        let rejected = FollowLinePayload::delivery(r#"{"version":3,"kind":"transition"}"#)
            .unwrap()
            .unwrap_err();

        assert_eq!(rejected, FollowLineRejected::UnsupportedVersion { version: 3 });
        assert!(rejected.to_string().contains("version 3"), "{rejected}");
    }
}

mod a_line_of_an_unknown_kind {
    use crate::domain::errors::FollowLineRejected;
    use crate::infrastructure::follow_line_payload::FollowLinePayload;

    #[test]
    fn is_rejected_naming_the_kind() {
        let rejected = FollowLinePayload::delivery(r#"{"version":2,"kind":"heartbeat"}"#)
            .unwrap()
            .unwrap_err();

        assert_eq!(
            rejected,
            FollowLineRejected::UnknownKind {
                kind: "heartbeat".to_string()
            }
        );
        assert!(rejected.to_string().contains("heartbeat"), "{rejected}");
    }
}

mod an_activity_line {
    use crate::infrastructure::follow_line_payload::FollowLinePayload;
    use crate::tests::infrastructure::follow_line_payload::RawTransition;

    #[test]
    fn is_read_and_delivers_nothing() {
        assert_eq!(FollowLinePayload::delivery(&RawTransition::activity()), None);
    }
}

mod a_version_1_line {
    use crate::infrastructure::follow_line_payload::FollowLinePayload;
    use crate::tests::infrastructure::follow_line_payload::RawLine;

    #[test]
    fn is_still_delivered_with_its_own_status_text() {
        let line = FollowLinePayload::delivery(&RawLine::valid()).unwrap().unwrap();

        assert_eq!(line.status(), "advancing");
        assert_eq!(line.step(), "run-controls");
    }
}
