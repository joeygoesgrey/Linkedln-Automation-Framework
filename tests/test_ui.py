"""Tests for the shared lookup helper and the miss record it keeps."""

from types import SimpleNamespace

from laf.ui import UiActions
from tests.fakes import FakeDriver, FakeElement

SELECTOR = "//button[@data-view-name='share-post']"


def _ui(elements: dict[str, FakeElement | None] | None = None) -> UiActions:
    """Build the helper over a fake driver with a short configured timeout.

    WHY
        The miss record is the only place the closing error line gets its count
        and page, so these tests need the real helper and no browser.

    Args
        elements: dict, the selector map the fake driver answers from.

    Returns
        UiActions, the helper over the fake driver.
    """
    config = SimpleNamespace(short_timeout=0.1)
    return UiActions(FakeDriver(elements=elements), config)  # type: ignore[arg-type]


def test_a_failed_lookup_records_the_miss() -> None:
    """A lookup that finds nothing keeps its candidates, page and wait.

    WHY
        The closing error line says how many selectors were tried and on which
        page, and it reads those three values from this record.
    """
    ui = _ui()

    assert ui.find_by_selectors([SELECTOR], "xpath", timeout=0.1) is None
    assert ui.last_miss is not None
    assert ui.last_miss.candidates == (SELECTOR,)
    assert ui.last_miss.page == "https://www.linkedin.com/feed/"
    assert ui.last_miss.seconds == 0.1


def test_a_found_lookup_leaves_the_miss_record_empty() -> None:
    """A lookup that finds the element records no miss.

    WHY
        A stale miss would point the user at a selector that works, and the
        closing line would name the wrong control.
    """
    ui = _ui({SELECTOR: FakeElement(text="Post")})

    assert ui.find_by_selectors([SELECTOR], "xpath", timeout=0.1) is not None
    assert ui.last_miss is None


def test_a_locator_pair_is_stored_as_plain_text() -> None:
    """A (strategy, text) pair reaches the record as readable text.

    WHY
        The record is printed inside a sentence, and a raw Python tuple there
        tells the user nothing.
    """
    ui = _ui()

    assert ui.find_by_selectors([("xpath", SELECTOR)], "xpath", timeout=0.1) is None
    assert ui.last_miss is not None
    assert ui.last_miss.candidates == (f"xpath {SELECTOR}",)
