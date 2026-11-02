"""Fake Selenium objects for tests, so no browser is ever needed."""

from typing import Any

from selenium.common.exceptions import NoSuchElementException


class FakeElement:
    """Stand in for a Selenium WebElement and record what happens to it."""

    def __init__(
        self,
        text: str = "",
        displayed: bool = True,
        enabled: bool = True,
        children: dict[str, "FakeElement | None"] | None = None,
        attributes: dict[str, str] | None = None,
    ) -> None:
        """Create an element with sensible defaults for tests.

        Args:
            text: the visible text of the element.
            displayed: whether `is_displayed` returns true.
            enabled: whether `is_enabled` returns true.
            children: selector to element map used by `find_element`.
            attributes: values returned by `get_attribute`.
        """
        self.text = text
        self.displayed = displayed
        self.enabled = enabled
        self.children = children or {}
        self.attributes = attributes or {}
        self.clicks = 0
        self.typed: list[str] = []
        self.cleared = 0

    def click(self) -> None:
        """Record one click."""
        self.clicks += 1

    def send_keys(self, value: str) -> None:
        """Record typed text, including Selenium key tokens."""
        self.typed.append(str(value))

    def clear(self) -> None:
        """Record one clear call."""
        self.cleared += 1

    def is_displayed(self) -> bool:
        """Report whether this element is visible."""
        return self.displayed

    def is_enabled(self) -> bool:
        """Report whether this element can be interacted with."""
        return self.enabled

    def get_attribute(self, name: str) -> str | None:
        """Return one configured attribute, or None."""
        return self.attributes.get(name)

    def find_element(self, by: str, selector: str) -> "FakeElement":
        """Return a configured child, or raise as Selenium would.

        Args:
            by: the Selenium lookup strategy.
            selector: the selector string.

        Raises:
            NoSuchElementException: when no child is configured for the selector.
        """
        child = self.children.get(selector)
        if child is None:
            raise NoSuchElementException(f"no child for {by}={selector}")
        return child

    def find_elements(self, by: str, selector: str) -> list["FakeElement"]:
        """Return the configured child as a list, or an empty list."""
        child = self.children.get(selector)
        return [] if child is None else [child]


class FakeDriver:
    """Stand in for a Selenium WebDriver and record every call."""

    def __init__(
        self,
        page_url: str = "https://www.linkedin.com/feed/",
        source: str = "",
        elements: dict[str, FakeElement | None] | None = None,
    ) -> None:
        """Create a driver with a starting URL and a selector map.

        Args:
            page_url: returned by `current_url` until `get` is called.
            source: returned by `page_source`.
            elements: selector to element map used by `find_element`.
        """
        self.current_url = page_url
        self.page_source = source
        self.elements = elements or {}
        self.visited: list[str] = []
        self.scripts: list[str] = []
        self.waits: list[int] = []
        self.quit_calls = 0
        self.closed = False

    def get(self, url: str) -> None:
        """Record a navigation and update `current_url`."""
        self.visited.append(url)
        self.current_url = url

    def find_element(self, by: str, selector: str) -> FakeElement:
        """Return a configured element, or raise as Selenium would.

        Args:
            by: the Selenium lookup strategy.
            selector: the selector string.

        Raises:
            NoSuchElementException: when no element is configured for the selector.
        """
        element = self.elements.get(selector)
        if element is None:
            raise NoSuchElementException(f"no element for {by}={selector}")
        return element

    def find_elements(self, by: str, selector: str) -> list[FakeElement]:
        """Return the configured element as a list, or an empty list."""
        element = self.elements.get(selector)
        return [] if element is None else [element]

    def execute_script(self, script: str, *args: Any) -> None:
        """Record a script call and change nothing."""
        self.scripts.append(script)

    def implicitly_wait(self, seconds: float) -> None:
        """Record a wait call."""
        self.waits.append(int(seconds))

    def quit(self) -> None:
        """Record one quit call."""
        self.quit_calls += 1
        self.closed = True
