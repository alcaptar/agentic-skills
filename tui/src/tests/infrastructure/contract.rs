use std::collections::BTreeSet;
use std::path::PathBuf;

use serde_json::Value;

pub struct LineContract {
    pub optional: BTreeSet<String>,
    pub examples: Vec<serde_json::Map<String, Value>>,
}

impl LineContract {
    pub fn on_disk(file: &str) -> Self {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("contract")
            .join(file);
        let document: Value = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
        let optional = document["optional"]
            .as_array()
            .unwrap()
            .iter()
            .map(|key| key.as_str().unwrap().to_string())
            .collect();
        let examples = document["examples"]
            .as_array()
            .unwrap()
            .iter()
            .map(|example| example.as_object().unwrap().clone())
            .collect();

        Self { optional, examples }
    }

    pub fn raw(example: &serde_json::Map<String, Value>) -> String {
        Value::Object(example.clone()).to_string()
    }
}

mod the_follow_line_contract {
    use crate::infrastructure::follow_line_payload::FollowLinePayload;
    use crate::tests::infrastructure::contract::LineContract;

    #[test]
    fn has_examples_and_every_one_parses() {
        let contract = LineContract::on_disk("follow-line.json");

        assert!(!contract.examples.is_empty());
        for example in &contract.examples {
            let parsed = FollowLinePayload::parsed(&LineContract::raw(example));
            assert!(parsed.is_ok(), "{example:?}: {parsed:?}");
        }
    }

    #[test]
    fn declares_every_key_the_interface_requires_as_present_and_not_optional() {
        let contract = LineContract::on_disk("follow-line.json");

        for key in FollowLinePayload::REQUIRED_KEYS {
            assert!(!contract.optional.contains(key), "{key} is optional in the contract");
            for example in &contract.examples {
                assert!(example.contains_key(key), "{key} missing from an example");
            }
        }
    }

    #[test]
    fn stops_parsing_when_a_required_key_is_taken_out_of_an_example() {
        let contract = LineContract::on_disk("follow-line.json");

        for key in FollowLinePayload::REQUIRED_KEYS {
            for example in &contract.examples {
                let mut without = example.clone();
                without.remove(key);

                let parsed = FollowLinePayload::parsed(&LineContract::raw(&without));

                assert!(parsed.is_err(), "taking {key} out of an example still parses");
            }
        }
    }
}

mod the_understanding_line_contract {
    use crate::domain::errors::UnderstandingUnread;
    use crate::infrastructure::understanding_line_payload::UnderstandingLinePayload;
    use crate::tests::infrastructure::contract::LineContract;

    #[test]
    fn has_examples_and_every_one_parses() {
        let contract = LineContract::on_disk("understanding-line.json");

        assert!(!contract.examples.is_empty());
        for example in &contract.examples {
            let parsed = UnderstandingLinePayload::parsed(&LineContract::raw(example));
            assert!(parsed.is_ok(), "{example:?}: {parsed:?}");
        }
    }

    #[test]
    fn stops_parsing_when_a_key_is_taken_out_of_an_example() {
        let contract = LineContract::on_disk("understanding-line.json");

        for example in &contract.examples {
            for key in example.keys() {
                let mut without = example.clone();
                without.remove(key);

                let parsed = UnderstandingLinePayload::parsed(&LineContract::raw(&without));

                assert!(
                    matches!(parsed, Err(UnderstandingUnread::WrongValue { .. })),
                    "taking {key} out of an example still parses"
                );
            }
        }
    }
}
