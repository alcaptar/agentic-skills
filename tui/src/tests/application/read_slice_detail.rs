mod the_events_of_a_slice {
    use crate::domain::follow_line::FollowLine;
    use crate::tests::application::watching::Watching;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;

    #[test]
    fn are_exactly_the_ones_received_for_it_in_arrival_order_and_none_of_another_slice() {
        let first = FollowLineMother::child_of(140, 150);
        let watched = Watching::one_tick(Watching::lines(vec![
            first.clone(),
            FollowLineMother::orphan(170),
            FollowLineMother::moved_to(&first, "implement"),
            FollowLineMother::closed(&first),
        ]));

        let row = watched.board().row(&Watching::key(150)).unwrap();

        let steps: Vec<&str> = row.events().iter().map(FollowLine::step).collect();
        assert_eq!(steps, vec!["run-controls", "implement", "await-merge"]);
    }
}

mod moving_the_selection {
    use crate::tests::application::watching::Watching;

    #[test]
    fn starts_at_the_first_slice_in_the_order_the_board_paints_them() {
        let watched = Watching::three_slices_in_two_groups();

        assert_eq!(watched.board().after(None), Some(Watching::key(150)));
        assert_eq!(watched.board().before(None), Some(Watching::key(150)));
    }

    #[test]
    fn walks_down_and_up_across_groups_and_stops_at_both_ends() {
        let watched = Watching::three_slices_in_two_groups();
        let board = watched.board();

        assert_eq!(board.after(Some(&Watching::key(150))), Some(Watching::key(160)));
        assert_eq!(board.after(Some(&Watching::key(160))), Some(Watching::key(170)));
        assert_eq!(board.after(Some(&Watching::key(170))), Some(Watching::key(170)));
        assert_eq!(board.before(Some(&Watching::key(170))), Some(Watching::key(160)));
        assert_eq!(board.before(Some(&Watching::key(150))), Some(Watching::key(150)));
    }

    #[test]
    fn finds_nothing_on_an_empty_board() {
        let watched = Watching::one_tick(vec![]);

        assert_eq!(watched.board().after(None), None);
    }
}

mod reading_the_detail {
    use crate::application::queries::read_slice_detail::ReadSliceDetail;
    use crate::domain::errors::UnderstandingUnread;
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::ScriptedUnderstandingSource;
    use crate::tests::mothers::understanding_mother::UnderstandingMother;

    #[test]
    fn asks_the_source_for_the_slice_it_was_given_and_carries_the_understanding() {
        let (source, asked) = ScriptedUnderstandingSource::answering(Ok(UnderstandingMother::published()));
        let mut read = ReadSliceDetail::new(source);

        let detail = read.execute(Watching::key(150));

        assert_eq!(*asked.borrow(), vec![Watching::key(150)]);
        assert_eq!(detail.key(), &Watching::key(150));
        assert_eq!(detail.understanding(), &Ok(UnderstandingMother::published()));
    }

    #[test]
    fn keeps_a_slice_without_a_published_understanding_as_a_value_and_not_as_a_failure() {
        let (source, _) = ScriptedUnderstandingSource::answering(Ok(UnderstandingMother::not_published()));

        let detail = ReadSliceDetail::new(source).execute(Watching::key(150));

        assert_eq!(detail.understanding(), &Ok(UnderstandingMother::not_published()));
    }

    #[test]
    fn carries_a_failed_read_inside_the_detail_instead_of_propagating_it() {
        let unread = UnderstandingUnread::CommandFailed {
            reason: "gh is not authenticated".to_string(),
        };
        let (source, _) = ScriptedUnderstandingSource::answering(Err(unread.clone()));

        let detail = ReadSliceDetail::new(source).execute(Watching::key(150));

        assert_eq!(detail.understanding(), &Err(unread));
    }
}
