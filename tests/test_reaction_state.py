"""Tests for reading the reaction state of a feed control.

WHY
    The new feed keeps the reaction state in the aria-label and no longer sets
    aria-pressed. A wrong read clicks an already liked post and removes the
    like, so the state check needs its own tests.
"""

from laf.services.engage_utils import reaction_already_set
from tests.fakes import FakeElement


def test_aria_pressed_true_reports_set() -> None:
    """
    WHY
        Older markup still reports the state with aria-pressed, and that path
        must keep working.
    """
    button = FakeElement(attributes={"aria-pressed": "true"})
    assert reaction_already_set(button) is True


def test_no_reaction_label_reports_unset() -> None:
    """
    WHY
        A post with no reaction must be clicked, so the "no reaction" label has
        to read as not set.
    """
    button = FakeElement(
        attributes={"aria-label": "Reaction button state: no reaction"}
    )
    assert reaction_already_set(button) is False


def test_chosen_reaction_label_reports_set() -> None:
    """
    WHY
        A label that names any reaction other than "no reaction" means the post
        is already liked, and clicking it again would remove the like.
    """
    button = FakeElement(
        attributes={"aria-label": "Reaction button state: like"}
    )
    assert reaction_already_set(button) is True


def test_nested_label_reports_set() -> None:
    """
    WHY
        In the comment row the label sits on the svg inside a div that acts as
        the button, so the check must read labels below the clicked element.
    """
    inner = FakeElement(
        attributes={"aria-label": "Reaction button state: celebrate"}
    )
    button = FakeElement(children={".//*[@aria-label]": inner})
    assert reaction_already_set(button) is True


def test_missing_labels_report_unset() -> None:
    """
    WHY
        An unknown control must not block the action, so no label and no
        aria-pressed reads as not set.
    """
    button = FakeElement()
    assert reaction_already_set(button) is False
