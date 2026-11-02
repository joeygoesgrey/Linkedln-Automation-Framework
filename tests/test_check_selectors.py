"""Tests for the selector checker helpers that need no browser."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from selenium.common.exceptions import InvalidSessionIdException

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import check_selectors  # noqa: E402


class _DeadDriver:
    """A driver whose browser has closed."""

    def execute_script(self, _script: str) -> int:
        raise InvalidSessionIdException("invalid session id")


class _LiveDriver:
    """A driver whose browser is still open."""

    def execute_script(self, _script: str) -> int:
        return 1


def test_ensure_browser_alive_aborts_on_a_closed_session() -> None:
    """A closed browser stops the run instead of reporting false fails.

    WHY
        The shared lookup helper treats a closed browser as a selector miss, so
        without this abort the report shows a page of fails for a page nobody
        looked at.
    """
    with pytest.raises(check_selectors.CheckerAborted):
        check_selectors.ensure_browser_alive(_DeadDriver())  # type: ignore[arg-type]


def test_ensure_browser_alive_passes_on_an_open_session() -> None:
    """An open browser lets the run continue."""
    check_selectors.ensure_browser_alive(_LiveDriver())  # type: ignore[arg-type]


def test_prepare_page_skips_the_pass_when_the_panel_control_is_missing() -> None:
    """A pass whose panel never opened is skipped, not reported as fails.

    WHY
        The composer selectors only exist inside the panel, so checking them
        without the panel open would print fails for correct selectors.
    """
    ui = SimpleNamespace(driver=_LiveDriver(), find_by_selectors=lambda *a, **k: None)

    assert check_selectors.prepare_page(ui, "composer") is False  # type: ignore[arg-type]


def test_composer_pass_skips_schedule_attributes() -> None:
    """The composer pass checks only the attributes in the open composer.

    WHY
        The schedule inputs do not exist until the schedule picker opens, so a
        composer pass that checked them would report false failures.
    """
    assert check_selectors.wants_attribute("composer", "POST_EDITOR") is True
    assert check_selectors.wants_attribute("composer", "SCHEDULE_BUTTONS") is False


def test_schedule_pass_checks_only_schedule_attributes() -> None:
    """The schedule pass checks only the schedule attributes.

    WHY
        The schedule picker hides the editor, so the editor would fail in that
        state even though its selector is correct.
    """
    assert check_selectors.wants_attribute("schedule", "SCHEDULE_DATE_INPUTS") is True
    assert check_selectors.wants_attribute("schedule", "POST_EDITOR") is False


def test_default_pass_checks_every_attribute() -> None:
    """A normal page entry checks every attribute of its class."""
    assert check_selectors.wants_attribute("all", "ANYTHING") is True


def test_build_pages_prepares_the_composer_once_and_the_schedule_after_it() -> None:
    """The composer passes run last and each leaves its panel open.

    WHY
        A feed level pass after the composer is open would measure the wrong
        page state, so the two composer passes must come last among the feed
        entries and the schedule pass must follow the composer pass.
    """
    config = SimpleNamespace(
        linkedin_base_url="https://www.linkedin.com/",
        linkedin_login_url="https://www.linkedin.com/login",
        linkedin_feed_url="https://www.linkedin.com/feed/",
    )
    pages = check_selectors.build_pages(config)  # type: ignore[arg-type]
    composer_indexes = [
        index
        for index, page in enumerate(pages)
        if page.selector_class.__name__ == "ComposerSelectors"
    ]

    assert [pages[index].prepare for index in composer_indexes] == ["composer", "schedule"]
    assert composer_indexes == list(range(len(pages) - 3, len(pages) - 1))
