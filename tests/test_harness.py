"""Prove the fake driver records calls and fails like Selenium."""

import pytest
from selenium.common.exceptions import NoSuchElementException

from tests.fakes import FakeDriver, FakeElement


def test_click_is_recorded(element: FakeElement) -> None:
    """A click on a fake element is counted."""
    element.click()
    element.click()
    assert element.clicks == 2


def test_typing_is_recorded(element: FakeElement) -> None:
    """Typed text is kept in order."""
    element.send_keys("hello")
    element.send_keys(" world")
    assert element.typed == ["hello", " world"]


def test_navigation_is_recorded(driver: FakeDriver) -> None:
    """A navigation is stored and changes the current URL."""
    driver.get("https://www.linkedin.com/feed/")
    assert driver.visited == ["https://www.linkedin.com/feed/"]
    assert driver.current_url.endswith("/feed/")


def test_missing_element_raises(driver: FakeDriver) -> None:
    """A selector that is not configured raises like Selenium."""
    with pytest.raises(NoSuchElementException):
        driver.find_element("xpath", "//button")
    assert driver.find_elements("xpath", "//button") == []


def test_configured_element_is_returned() -> None:
    """A configured selector returns its element."""
    button = FakeElement(text="Post")
    driver = FakeDriver(elements={"//button[@type='submit']": button})
    found = driver.find_element("xpath", "//button[@type='submit']")
    assert found is button
    assert found.text == "Post"
