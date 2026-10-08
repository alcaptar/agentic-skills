mod grouping {
    use crate::domain::parent::Parent;
    use crate::tests::application::watching::Watching;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;
    #[test]
    fn two_parents_of_the_same_repo_and_a_slice_without_parent_make_exactly_three_groups() {
        let watched = Watching::one_tick(Watching::lines(vec![
            FollowLineMother::orphan(170),
            FollowLineMother::child_of(141, 160),
            FollowLineMother::child_of(140, 150),
        ]));

        let groups: Vec<(String, Parent)> = watched
            .board()
            .groups()
            .iter()
            .map(|group| (group.repo().to_string(), group.parent()))
            .collect();

        assert_eq!(
            groups,
            vec![
                (FollowLineMother::REPO.to_string(), Parent::Issue(140)),
                (FollowLineMother::REPO.to_string(), Parent::Issue(141)),
                (FollowLineMother::REPO.to_string(), Parent::Absent),
            ]
        );
    }

    #[test]
    fn the_same_parent_number_in_two_repos_makes_two_groups() {
        let watched = Watching::one_tick(Watching::lines(vec![
            FollowLineMother::child_of_in_repo("alcaptar/one", 140, 150),
            FollowLineMother::child_of_in_repo("alcaptar/two", 140, 150),
        ]));

        assert_eq!(watched.board().groups().len(), 2);
    }
}

mod a_slice_that_reappears {
    use crate::application::queries::watch_slices::WatchSlices;
    use crate::domain::parent::Parent;
    use crate::domain::slice_board::SliceBoard;
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::ScriptedFollowSource;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;
    #[test]
    fn keeps_a_single_row_with_the_state_of_the_second_line() {
        let first = FollowLineMother::child_of(140, 150);
        let second = FollowLineMother::closed(&first);

        let watched = Watching::one_tick(Watching::lines(vec![first, second]));

        let groups = watched.board().groups();
        assert_eq!(groups.len(), 1);
        assert_eq!(groups[0].rows().len(), 1);
        assert_eq!(groups[0].rows()[0].step(), "await-merge");
        assert_eq!(groups[0].rows()[0].status(), "closed");
    }

    #[test]
    fn updates_across_ticks_without_duplicating_the_row() {
        let first = FollowLineMother::child_of(140, 150);
        let second = FollowLineMother::closed(&first);
        let mut watch = WatchSlices::new(ScriptedFollowSource::delivering(vec![
            Watching::lines(vec![first]),
            Watching::lines(vec![second]),
        ]));

        let after_first = watch.execute(SliceBoard::empty());
        let after_second = watch.execute(after_first.into_board());

        let groups = after_second.board().groups();
        assert_eq!(groups[0].rows().len(), 1);
        assert_eq!(groups[0].rows()[0].status(), "closed");
    }

    #[test]
    fn keeps_the_last_known_parent_and_name_when_the_later_line_arrives_without_them() {
        let first = FollowLineMother::child_of(140, 150);
        let second = FollowLineMother::closed_without_parent_or_name(&first);

        let watched = Watching::one_tick(Watching::lines(vec![first, second]));

        let groups = watched.board().groups();
        assert_eq!(groups.len(), 1);
        assert_eq!(groups[0].parent(), Parent::Issue(140));
        assert_eq!(groups[0].rows()[0].name(), Some(FollowLineMother::NAME));
        assert_eq!(groups[0].rows()[0].status(), "closed");
    }
}

mod a_rejected_line {
    use crate::application::queries::watch_slices::WatchSlices;
    use crate::domain::slice_board::SliceBoard;
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::ScriptedFollowSource;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;
    #[test]
    fn is_reported_without_losing_the_slices_already_listed() {
        let watched = Watching::one_tick(vec![
            Ok(FollowLineMother::child_of(140, 150)),
            Err(Watching::wrong_issue()),
        ]);

        assert_eq!(watched.rejection(), Some(&Watching::wrong_issue()));
        assert_eq!(watched.board().groups().len(), 1);
    }

    #[test]
    fn stays_reported_on_a_tick_with_nothing_new() {
        let mut watch = WatchSlices::new(ScriptedFollowSource::delivering(vec![
            vec![Err(Watching::wrong_issue())],
            vec![],
        ]));

        let after_rejection = watch.execute(SliceBoard::empty());
        let quiet = watch.execute(after_rejection.into_board());

        assert_eq!(quiet.rejection(), Some(&Watching::wrong_issue()));
    }

    #[test]
    fn is_cleared_when_a_valid_line_arrives_afterwards() {
        let watched = Watching::one_tick(vec![Err(Watching::wrong_issue()), Ok(FollowLineMother::orphan(170))]);

        assert_eq!(watched.rejection(), None);
    }
}
