"""Tests for the repost menu labels.

WHY
    The menu has two rows, and only one opens the editor. A candidate list that
    misses "Repost with thoughts" or matches "Repost instantly" sends the run to
    the wrong action, so the labels need a guard.
"""

from laf.selectors.feed import FeedActionSelectors as Selectors


def _matches(label: str) -> bool:
    """Report whether any candidate text appears in a menu label.

    WHY
        The service picks a row with a plain substring check, so the test uses
        the same rule against the real candidate list.

    Args
        label: str, the visible menu row text.

    Returns
        bool, True when one candidate appears in the label.
    """
    lowered = label.lower()
    return any(candidate in lowered for candidate in Selectors.REPOST_CANDIDATE_TEXTS)


def test_thoughts_row_matches() -> None:
    """
    WHY
        Without this label in the list, the run clicks nothing and the repost
        flow stops after opening the menu.
    """
    assert _matches("Repost with thoughts") is True


def test_instant_row_does_not_match() -> None:
    """
    WHY
        Matching the instant row would share the post without the user's words,
        which is the wrong action.
    """
    assert _matches("Repost instantly") is False


def test_submit_buttons_all_say_repost() -> None:
    """
    WHY
        The repost modal has no Post or Share button. A dead submit selector
        costs a six second wait and then still finds nothing.
    """
    submit = [item.lower() for item in Selectors.SUBMIT_REPOST]
    assert submit
    assert all("repost" in item for item in submit)
