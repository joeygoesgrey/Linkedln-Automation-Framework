"""Tests for the click fallback log lines.

WHY
    Selenium exceptions carry a full Java stack trace. A click that recovers
    through a fallback is a normal event, so the log must name the cause in one
    line and never print the trace to the console.
"""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.webelement import WebElement

from laf.ui import UiActions
from tests.fakes import FakeDriver


def _ui(driver: FakeDriver) -> UiActions:
    """Build the helper over a fake driver.

    WHY
        The click fallback needs a driver for script and action chain calls, and
        a fake keeps the test free of a browser.

    Args
        driver: FakeDriver, the stand in for the browser.

    Returns
        UiActions, the helper over the fake driver.
    """
    config = SimpleNamespace(short_timeout=0.1)
    return UiActions(driver, config)  # type: ignore[arg-type]


def _clickable() -> MagicMock:
    """Build an object that passes the WebElement check.

    WHY
        The helper rejects anything that is not a WebElement before it tries a
        click, so the test needs a stand in that passes that check.

    Returns
        MagicMock, an object typed as a WebElement.
    """
    return MagicMock(spec=WebElement)


def test_recovered_click_logs_one_line_without_trace(caplog) -> None:
    """
    WHY
        The user saw twenty Java frames for a click that worked. A recovered
        fallback must log the cause in one line and nothing else.
    """
    caplog.set_level(logging.INFO, logger="laf.ui")
    driver = FakeDriver()
    element = _clickable()
    element.click.side_effect = WebDriverException(
        "element click intercepted\nStacktrace:\n#0 driver frame\n#1 driver frame"
    )

    assert _ui(driver).click_with_fallback(element, "Like (stream)") is True
    assert "intercepted" in caplog.text
    assert "using JavaScript" in caplog.text
    assert "Stacktrace" not in caplog.text


def test_failed_click_logs_short_error_and_hides_trace(caplog) -> None:
    """
    WHY
        When every strategy fails, the user still deserves one readable line.
        The Java trace stays out, and the Python trace goes to debug only.
    """
    caplog.set_level(logging.INFO, logger="laf.ui")
    driver = FakeDriver()
    driver.execute_script = MagicMock(  # type: ignore[method-assign]
        side_effect=WebDriverException("script failed\nStacktrace:\n#0 driver frame")
    )
    element = _clickable()
    element.click.side_effect = WebDriverException(
        "element click intercepted\nStacktrace:\n#0 driver frame"
    )

    chain = MagicMock()
    chain.move_to_element.return_value = chain
    chain.click.return_value = chain
    chain.perform.side_effect = WebDriverException(
        "actions failed\nStacktrace:\n#0 driver frame"
    )

    with patch("laf.ui.ActionChains", return_value=chain):
        result = _ui(driver).click_with_fallback(element, "Like (stream)")

    assert result is False
    assert "actions failed" in caplog.text
    assert "WebDriverException" in caplog.text
    assert "Stacktrace" not in caplog.text
