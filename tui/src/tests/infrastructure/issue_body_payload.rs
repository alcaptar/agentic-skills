mod the_issue_body_payload {
    use crate::domain::errors::IssuesUnread;
    use crate::infrastructure::issue_body_payload::IssueBodyPayload;

    #[test]
    fn gives_the_body_of_the_literal_answer_of_gh() {
        assert_eq!(
            IssueBodyPayload::parsed(r#"{"body":"uno\n\n<!-- m -->"}"#),
            Ok("uno\n\n<!-- m -->".to_string())
        );
    }

    #[test]
    fn text_that_is_not_json_is_not_json() {
        assert!(matches!(
            IssueBodyPayload::parsed("nope"),
            Err(IssuesUnread::NotJson { .. })
        ));
    }

    #[test]
    fn a_body_that_is_not_a_string_is_a_wrong_value() {
        assert!(matches!(
            IssueBodyPayload::parsed(r#"{"body":3}"#),
            Err(IssuesUnread::WrongValue { key, .. }) if key == "body"
        ));
    }

    #[test]
    fn a_key_that_was_not_asked_for_is_a_wrong_value() {
        assert!(matches!(
            IssueBodyPayload::parsed(r#"{"body":"x","title":"y"}"#),
            Err(IssuesUnread::WrongValue { key, .. }) if key == "title"
        ));
    }
}
