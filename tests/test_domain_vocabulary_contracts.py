"""Contracts between two vocabularies of the program's own domain, with no document in between.

`RunState` and `Step` project onto `IssueLabel` through `IssueLabel.of`, and every piece involved
lives inside `slice_runner.domain`. Nothing here compares a script or a skill against prose: it
compares two closed vocabularies of code, which is what `docs/conventions/domain.md` cites this
file for.
"""

from __future__ import annotations

from slice_runner.domain.check_verdict import CheckVerdict
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step


def test_every_runstate_closure_the_translator_is_asked_about_returns_a_label_or_none_only_for_merged() -> None:
    """The translator from `RunState` to a GitHub label pays the debt `domain.md` declared.

    `RunState` duplicated, in English, what `issue_body.Estado`/`MotivoBloqueada` said in Spanish
    before that script was retired for having no consumer, and nothing compared the two sides until
    the translator that writes to a subissue existed. `MERGED` is the one closure with no label on
    purpose -- GitHub closes the issue itself when the pull request merges -- so it is the sole `None`
    this loop may see; any other closure coming back empty is a step the translator forgot to project.
    """
    for state in RunState:
        if state is RunState.OPEN:
            continue
        label = IssueLabel.of(state=state, step=Step.IMPLEMENT)
        if state is RunState.MERGED:
            assert label is None, "MERGED closes the issue on GitHub's side and must carry no label"
        else:
            assert label in set(IssueLabel), f"{state} projects to {label!r}, which is not a label the vocabulary knows"


def test_no_label_in_the_vocabulary_lacks_a_source_in_the_translator_or_a_manual_entry_point() -> None:
    """A manual-source label is not "a person writes it": it is any label that something other
    than `IssueLabel.of` writes, because it happens outside the `(RunState, Step)` pair the
    translator knows about. `PENDING` is the only one: a person writes it by hand when they
    create a subissue (`CLAUDE.md`'s slice). `AWAITING_ALIGNMENT` projects from
    `(RunState.OPEN, Step.UNDERSTAND)` like any other label -- `GhRunRepository.pause_for_alignment`
    still writes it the very first time, before any `Run` exists to project from, but the value it
    writes is the same one the translator already knows for that step. Every other member has to
    come out of some `(RunState, Step)` pair the translator projects, or it is dead vocabulary
    nobody ever writes.
    """
    manual_source = {IssueLabel.PENDING}
    produced = {IssueLabel.of(state=state, step=step) for state in RunState for step in Step} - {None}

    assert set(IssueLabel) - produced == manual_source


def test_the_verdict_vocabulary_of_the_doctor_holds_only_the_verdicts_a_check_produces_today() -> None:
    """`CheckVerdict` closes over exactly `ready`, `warning` and `missing`.

    `slice-runner doctor` runs a check without a `MISSING`/`WARNING` split for git, gh, claude and
    the two skills, `MISSING` for an unreadable `--repo`, and `WARNING` for a `--base` that is
    behind its remote -- a base that lags does not block the run the way a missing tool does.
    Adding a member here without a check that produces it would be dead vocabulary nobody ever
    emits, exactly the failure `IssueLabel`'s own contract above guards against for a different
    vocabulary.
    """
    assert set(CheckVerdict) == {CheckVerdict.READY, CheckVerdict.WARNING, CheckVerdict.MISSING}
