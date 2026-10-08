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
