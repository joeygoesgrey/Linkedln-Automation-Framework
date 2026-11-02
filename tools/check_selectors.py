"""Read-only selector checker for the LinkedIn pages the bot uses.

Report which selectors still match the live page after a LinkedIn markup
change, so a person sees what broke before a real run. Opens each page once,
tries every selector of the classes for that page, and prints one line per
selector. It only looks elements up and clicks controls that open a panel. It
never types, posts, or schedules anything.
"""

import time
from dataclasses import dataclass
from typing import Iterator, Sequence

from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from laf.browser.driver import DriverFactory
from laf.config import Config, load_config
from laf.errors import LAFError
from laf.messages import render
from laf.selectors.composer import ComposerSelectors
from laf.selectors.engage import EngageSelectors
from laf.selectors.feed import FeedActionSelectors, PostExtractorSelectors
from laf.selectors.login import LoginSelectors
from laf.selectors.media import MediaSelectors
from laf.selectors.mentions import MentionSelectors
from laf.selectors.overlays import OverlaySelectors
from laf.selectors.profile import ProfileSelectors
from laf.selectors.verify import VerifySelectors
from laf.ui import UiActions

VALID_BY = {
    value
    for name, value in vars(By).items()
    if not name.startswith("_") and isinstance(value, str)
}

ATTEMPT_TIMEOUT = 2.0
PAGE_LOAD_TIMEOUT = 30
COMPOSER_OPEN_PAUSE = 4.0
SCHEDULE_OPEN_PAUSE = 3.0


@dataclass(frozen=True)
class PageCheck:
    """One page visit and the selectors to try on it."""

    page: str
    url: str
    selector_class: type
    prepare: str = "none"
    wanted: str = "all"


class CheckerAborted(Exception):
    """Raised when the browser is gone and the report can no longer be trusted.

    WHY
        The shared lookup helper treats a closed browser as a selector miss, so
        without this error the report shows page after page of "fail" lines for
        selectors nobody actually looked for.
    """


def build_pages(config: Config) -> list[PageCheck]:
    """
    WHY
        One list keeps the page, its URL, and its selector classes in one place,
        so adding a page or a class is a single line. The composer selectors
        only exist inside the open composer, so their two passes run last, one
        after a click opens the composer and one after a click opens the
        schedule picker.

    Args
        config: Config, the frozen runtime settings that hold the page URLs.

    Returns
        list[PageCheck], one entry per page visit and selector class.
    """
    feed = config.linkedin_feed_url
    search = config.linkedin_base_url + "search/results/people/"
    return [
        PageCheck("login", config.linkedin_login_url, LoginSelectors),
        PageCheck("feed", feed, VerifySelectors),
        PageCheck("feed", feed, OverlaySelectors),
        PageCheck("feed", feed, MediaSelectors),
        PageCheck("feed", feed, MentionSelectors),
        PageCheck("feed", feed, PostExtractorSelectors),
        PageCheck("feed", feed, FeedActionSelectors),
        PageCheck("feed", feed, EngageSelectors),
        PageCheck("feed", feed, ComposerSelectors, "composer", "composer"),
        PageCheck("feed", feed, ComposerSelectors, "schedule", "schedule"),
        PageCheck("profile", search, ProfileSelectors),
    ]


def wants_attribute(wanted: str, attribute: str) -> bool:
    """
    WHY
        The schedule selectors and the composer selectors live in two different
        panel states, so each pass checks only the attributes that exist in its
        state and never reports a false failure for the other panel.

    Args
        wanted: str, "all", "composer" or "schedule", from the page entry.
        attribute: str, the selector attribute name from the class.

    Returns
        bool, True when this attribute belongs to the pass.
    """
    is_schedule = attribute.startswith("SCHEDULE_")
    if wanted == "composer":
        return not is_schedule
    if wanted == "schedule":
        return is_schedule
    return True


def ensure_browser_alive(driver: WebDriver) -> None:
    """
    WHY
        Stop the run the moment the browser closes, because every selector after
        that point would be reported as a fail for a page that is not open.

    Args
        driver: WebDriver, the Selenium driver for the run.

    Raises
        CheckerAborted: when the browser or the driver session has closed.
    """
    try:
        driver.execute_script("return 1")
    except (InvalidSessionIdException, NoSuchWindowException) as error:
        raise CheckerAborted(str(error)) from error


def load_page(driver: WebDriver, url: str) -> None:
    """
    WHY
        A page that cannot be opened must stop the run as a named abort, not
        surface as a raw Selenium traceback.

    Args
        driver: WebDriver, the Selenium driver for the run.
        url: str, the page address to open.

    Raises
        CheckerAborted: when the browser closed before the page could open.
        TimeoutException: when the page does not finish loading.
    """
    try:
        driver.get(url)
    except (InvalidSessionIdException, NoSuchWindowException) as error:
        raise CheckerAborted(str(error)) from error
    wait_for_page(driver)


def click_first_selector(ui: UiActions, selectors: Sequence[str]) -> bool:
    """
    WHY
        The composer and schedule selectors only exist after their panel opens,
        so the checker must press the control that opens it with the same
        selector list the bot uses.

    Args
        ui: UiActions, the shared lookup helper.
        selectors: Sequence[str], the ordered selector list for the control.

    Returns
        bool, True when a control was found and clicked.
    """
    control = ui.find_by_selectors(selectors, By.XPATH, timeout=ATTEMPT_TIMEOUT)
    if control is None:
        return False
    control.click()
    return True


def prepare_page(ui: UiActions, prepare: str) -> bool:
    """
    WHY
        A page entry says which panel must be open before its selectors are
        checked, and this runs that one click so each pass measures the state it
        claims to measure. A pass whose panel did not open is skipped instead of
        printing a page of false fails.

    Args
        ui: UiActions, the shared lookup helper.
        prepare: str, "none", "composer" or "schedule".

    Returns
        bool, True when the required panel is open or none was required, False
        when a control needed to open it was not found.

    Raises
        CheckerAborted: when the browser closed during the click or the wait.

    MUTATIONS
        clicks one control on the open page and waits for the panel.
    """
    if prepare == "none":
        return True
    ensure_browser_alive(ui.driver)
    editor = ui.find_by_selectors(ComposerSelectors.POST_EDITOR, By.XPATH, timeout=1.0)
    if editor is None:
        if not click_first_selector(ui, ComposerSelectors.START_POST_TRIGGERS):
            print("prepare failed: the Start a post control was not found")
            return False
        time.sleep(COMPOSER_OPEN_PAUSE)
    if prepare == "schedule":
        if not click_first_selector(ui, ComposerSelectors.SCHEDULE_BUTTONS):
            print("prepare failed: the schedule control was not found")
            return False
        time.sleep(SCHEDULE_OPEN_PAUSE)
    ensure_browser_alive(ui.driver)
    return True


def is_locator_tuple(value: object) -> bool:
    """
    WHY
        A tuple attribute may be one (By, str) locator or a group of locator
        strings, and the two need different handling.

    Args
        value: object, the raw value of a selector attribute.

    Returns
        bool, True when the value is a single (By, str) locator.
    """
    return isinstance(value, tuple) and len(value) == 2 and value[0] in VALID_BY


def iter_locator_pairs(value: object) -> Iterator[object]:
    """
    WHY
        Selector attributes appear as a bare string, a list, or a tuple group,
        and the checker has to reach every locator in all three shapes.

    Args
        value: object, the raw value of a selector attribute.

    Returns
        Iterator[object], each locator, as a string or a (By, str) tuple.
    """
    if isinstance(value, str):
        yield value
        return
    if is_locator_tuple(value):
        yield value
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield item


def is_empty_collection(value: object) -> bool:
    """
    WHY
        A class with an empty selector list must be reported as empty instead of
        crashing or looking like a failure.

    Args
        value: object, the raw value of a selector attribute.

    Returns
        bool, True when the value is an empty list or tuple that is not a
        locator.
    """
    return isinstance(value, (list, tuple)) and len(value) == 0 and not is_locator_tuple(value)


def guess_strategy(selector: str) -> str:
    """
    WHY
        A bare string selector does not say whether it is XPath or CSS, and the
        webdriver needs the right strategy to look it up.

    Args
        selector: str, a bare selector string.

    Returns
        str, By.XPATH for XPath looking strings, otherwise By.CSS_SELECTOR.
    """
    stripped = selector.lstrip()
    if stripped.startswith(("/", "./", "(", "ancestor")):
        return By.XPATH
    return By.CSS_SELECTOR


def resolve_locator(locator: object) -> tuple[str, str]:
    """
    WHY
        Callers need a strategy and a selector string no matter which shape the
        stored locator has.

    Args
        locator: object, a selector string or a (By, str) tuple, as stored on a
            selector class.

    Returns
        tuple[str, str], the Selenium strategy and the selector text.

    Raises
        ValueError: when the locator is neither a string nor a pair of strings,
            which means the selector class holds a value the checker cannot use.
    """
    if isinstance(locator, tuple):
        by, text = locator
        if isinstance(by, str) and isinstance(text, str):
            return by, text
        raise ValueError(f"selector pair must be two strings, got {locator!r}")
    if isinstance(locator, str):
        return guess_strategy(locator), locator
    raise ValueError(f"selector must be a string or a pair, got {locator!r}")


def wait_for_page(driver: WebDriver) -> None:
    """
    WHY
        Selectors tried before the page finishes loading would report false
        failures.

    Args
        driver: WebDriver, the Selenium driver for the open page.

    Raises
        TimeoutException: when the page does not reach the complete state
        within PAGE_LOAD_TIMEOUT.
    """
    WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
        lambda current: current.execute_script("return document.readyState") == "complete"
    )


def selector_exists(ui: UiActions, by: str, selector: str) -> bool:
    """
    WHY
        One missing selector must be a fail line in the report, never a crash
        that hides the rest of the page.

    Args
        ui: UiActions, the shared lookup helper.
        by: str, the Selenium locator strategy.
        selector: str, the selector text.

    Returns
        bool, True when the element was found within the attempt timeout.
    """
    found = ui.find_by_selectors([(by, selector)], by, timeout=ATTEMPT_TIMEOUT)
    return found is not None


def check_attribute(
    ui: UiActions, page: str, class_name: str, attribute: str, value: object
) -> tuple[int, int]:
    """
    WHY
        Report one line per selector so a person can see exactly which locator
        still matches and which one needs updating.

    Args
        ui: UiActions, the shared lookup helper.
        page: str, the page name.
        class_name: str, the selector class name.
        attribute: str, the selector attribute name.
        value: object, the raw value of that attribute.

    Returns
        tuple[int, int], how many selectors were checked, and how many failed.

    MUTATIONS
        Prints one report line per selector, or one empty line when the
        attribute holds an empty collection.
    """
    if is_empty_collection(value):
        print(f"page={page} class={class_name} attribute={attribute} result=empty")
        return (0, 0)

    pairs = list(iter_locator_pairs(value))
    checked = 0
    failed = 0
    for index, locator in enumerate(pairs):
        by, selector = resolve_locator(locator)
        passed = selector_exists(ui, by, selector)
        checked += 1
        if not passed:
            failed += 1
        result = "pass" if passed else "fail"
        label = attribute if len(pairs) == 1 else f"{attribute}[{index}]"
        print(f"page={page} class={class_name} attribute={label} result={result}")
    return (checked, failed)


def check_class(
    ui: UiActions, page: str, selector_class: type, wanted: str = "all"
) -> tuple[int, int]:
    """
    WHY
        Run every selector of one class so a page change gives a full picture
        for that page in one pass, limited to the attributes that exist in the
        panel state the caller prepared.

    Args
        ui: UiActions, the shared lookup helper.
        page: str, the page name.
        selector_class: type, the selector class to check.
        wanted: str, "all", "composer" or "schedule", the attribute group to
            check.

    Returns
        tuple[int, int], how many selectors were checked, and how many failed.

    MUTATIONS
        Prints the report lines for every checked selector of the class.
    """
    checked = 0
    failed = 0
    for attribute, value in vars(selector_class).items():
        if attribute.startswith("__"):
            continue
        if not wants_attribute(wanted, attribute):
            continue
        class_checked, class_failed = check_attribute(
            ui, page, selector_class.__name__, attribute, value
        )
        checked += class_checked
        failed += class_failed
    return (checked, failed)


def main() -> int:
    """
    WHY
        Give the user one command that opens each page and prints the report.
        A driver setup failure is turned into one printed line and exit code 1
        instead of a traceback, a closed browser stops the run as a named abort
        instead of a page of false fails, and the browser is always closed
        afterwards.

    Returns
        int, 0 when every selector matched, 1 when the driver could not start,
        a selector failed or a pass was skipped, 2 when the browser closed
        before the run finished.

    Raises
        TimeoutException: when a page does not finish loading within
        PAGE_LOAD_TIMEOUT.
    """
    config = load_config()
    try:
        driver = DriverFactory.setup_driver(config)
    except LAFError as error:
        message, hint = render(error)
        print(f"{message} {hint} [{error.code}]")
        return 1
    ui = UiActions(driver, config)
    total_checked = 0
    total_failed = 0
    total_skipped = 0
    try:
        try:
            current_url = None
            for check in build_pages(config):
                ensure_browser_alive(driver)
                if check.url != current_url:
                    load_page(driver, check.url)
                    current_url = check.url
                if not prepare_page(ui, check.prepare):
                    print(
                        f"page={check.page} class={check.selector_class.__name__} "
                        "result=skipped (the panel did not open)"
                    )
                    total_skipped += 1
                    continue
                class_checked, class_failed = check_class(
                    ui, check.page, check.selector_class, check.wanted
                )
                total_checked += class_checked
                total_failed += class_failed
        except CheckerAborted as error:
            print(
                f"ABORT: the browser session closed ({error}). "
                "The report stops here and the lines above are the only valid ones."
            )
            return 2
    finally:
        driver.quit()
    print(
        f"{total_checked} selectors checked, "
        f"{total_checked - total_failed} passed, {total_failed} failed, "
        f"{total_skipped} passes skipped"
    )
    return 1 if (total_failed or total_skipped) else 0


if __name__ == "__main__":
    raise SystemExit(main())
