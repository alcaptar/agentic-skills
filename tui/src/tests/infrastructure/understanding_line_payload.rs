mod a_line_of_the_contract_shape {
    use crate::domain::errors::UnderstandingUnread;
    use crate::infrastructure::understanding_line_payload::UnderstandingLinePayload;
    use crate::tests::mothers::understanding_mother::UnderstandingMother;

    #[test]
    fn becomes_the_published_understanding_with_its_text_untouched() {
        let raw = serde_json::json!({"version": 1, "text": UnderstandingMother::TEXT}).to_string();

        assert_eq!(
            UnderstandingLinePayload::parsed(&raw),
            Ok(UnderstandingMother::published())
        );
    }

    #[test]
    fn is_rejected_when_the_other_side_adds_a_key_because_this_contract_is_ours() {
        let raw = r#"{"version":1,"text":"x","something_new":true}"#;

        let rejected = UnderstandingLinePayload::parsed(raw).unwrap_err();

        assert!(
            matches!(rejected, UnderstandingUnread::WrongValue { ref key, .. } if key == "something_new"),
            "{rejected:?}"
        );
    }

    #[test]
    fn is_rejected_naming_the_key_when_the_text_is_not_a_string() {
        let rejected = UnderstandingLinePayload::parsed(r#"{"version":1,"text":7}"#).unwrap_err();

        assert!(
            matches!(rejected, UnderstandingUnread::WrongValue { ref key, .. } if key == "text"),
            "{rejected:?}"
        );
    }

    #[test]
    fn is_rejected_when_something_that_is_not_json_arrives() {
        assert!(matches!(
            UnderstandingLinePayload::parsed("Traceback (most recent call last)"),
            Err(UnderstandingUnread::NotJson { .. })
        ));
    }
}
