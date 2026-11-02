"""Selenium action helpers shared by the LinkedIn service classes.

WHY
  Keep common utilities (delays, element lookup, resilient clicking) in one
  place so every service reaches the driver and the config the same way.
"""

import logging
import random
import time
from dataclasses import dataclass
from typing import Iterable, Optional, Union

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from laf.config import Config

logger = logging.getLogger(__name__)


def _error_summary(error: WebDriverException) -> str:
    """Make a short, one line report of a Selenium error for a log message.

    WHY
      Selenium's exception text carries a full Java stack trace, which fills the
      user's terminal and buries the reason. The class name and the first line
      of the message name the failure without the noise.

    Args
      error: WebDriverException, the raised error to describe.

    Returns
      str, the exception class name and the first message line, capped at 160
      characters.
    """
    raw = (getattr(error, "msg", None) or str(error) or "").strip()
    first_line = raw.splitlines()[0].strip() if raw else ""
    if first_line.startswith("Message: "):
        first_line = first_line[len("Message: ") :]
    if len(first_line) > 160:
        first_line = first_line[:157] + "..."
    if not first_line:
        return type(error).__name__
    return f"{type(error).__name__}: {first_line}"


@dataclass(frozen=True)
class SelectorMiss:
    """The last lookup that found nothing, kept for the closing error line.

    WHY
      A user who sees "the composer did not open" needs to know how many
      selectors were tried and on which page, without opening a Python trace.
    """

    candidates: tuple[str, ...]
    page: str
    seconds: float


def selector_text(candidate: Union[str, tuple]) -> str:
    """
    WHY
        A miss record holds plain text so it can be printed without a Python
        tuple in the middle of a sentence.

    Args
        candidate: Union[str, tuple], one stored selector, either a bare string
            or a (strategy, text) pair.

    Returns
        str, the strategy and the selector text for a pair, else the string.
    """
    if isinstance(candidate, tuple) and len(candidate) == 2:
        return f"{candidate[0]} {candidate[1]}"
    return str(candidate)


class UiActions:
    """Small Selenium actions that every service shares.

    WHY
      Give every service one object for driver access, human pacing, element
      lookup and resilient clicks, so those rules live in one place.
    """

    def __init__(self, driver: WebDriver, config: Config) -> None:
        """
        WHY
          Give every service one object for driver access, human pacing, element
          lookup and resilient clicks so those rules live in one place.

        Args
          driver: WebDriver, the active Selenium driver.
          config: Config, the frozen runtime settings.

        Raises
          ValueError: when driver is None.

        MUTATIONS
          stores the driver, the config and the last miss record on the
          instance.
        """
        # Standard 3: Basic validation
        if driver is None:
            raise ValueError("UiActions requires a valid WebDriver instance.")
        self.driver = driver
        self.config = config
        self.last_miss: Optional[SelectorMiss] = None

    def pause(
        self, min_delay: Optional[float] = None, max_delay: Optional[float] = None
    ) -> None:
        """Pause execution for a random interval within human bounds.

        WHY
          Mimic natural behaviour to reduce bot detection risk, and clamp a
          negative delay so the sleep call never receives a bad range.

        Args
          min_delay: Optional[float], the minimum seconds from the caller, or
            None to use the config.
          max_delay: Optional[float], the maximum seconds from the caller, or
            None to use the config.
        """
        # Standard 3: Basic validation
        actual_min = min_delay if min_delay is not None else self.config.min_action_delay
        actual_max = max_delay if max_delay is not None else self.config.max_action_delay

        if actual_min < 0 or actual_max < 0:
            logger.warning(
                f"Negative delay requested: min={actual_min}, max={actual_max}. Defaulting to 0."
            )
            actual_min, actual_max = max(0, actual_min), max(0, actual_max)

        time.sleep(random.uniform(actual_min, actual_max))

    def type_with_delays(self, element: WebElement, text: str) -> None:
        """Send text to a DOM element character-by-character with delays.

        WHY
          Emulate human typing to avoid triggering LinkedIn's bot heuristics.

        Args
          element: WebElement, the target field from the caller.
          text: str, the content to type.

        Raises
          TypeError: when element is not a WebElement.

        MUTATIONS
          types each character into the element and sleeps between keys.
        """
        # Standard 3: Basic validation
        if not isinstance(element, WebElement):
            raise TypeError(f"Expected WebElement, got {type(element)}")
        if not isinstance(text, str):
            text = str(text)

        for ch in text:
            element.send_keys(ch)
            self.pause(self.config.min_typing_delay, self.config.max_typing_delay)

    def find_by_selectors(
        self,
        selectors: Iterable[Union[str, tuple]],
        selector_type: str,
        timeout: Optional[float] = None,
    ) -> Optional[WebElement]:
        """Locate an element by iterating through multiple selector options.

        WHY
          Try each candidate locator until one is visible, so a change to one
          selector on the page does not break the action.

        Args
          selectors: Iterable[Union[str, tuple]], the candidate locators from
            the caller.
          selector_type: str, the Selenium strategy used for plain string
            locators.
          timeout: Optional[float], the seconds to wait, or None to use the
            config.

        Returns
          Optional[WebElement], the first visible match, or None when none
          matched.

        MUTATIONS
          records the miss, with the candidates, the page and the wait, on the
          instance so the closing error line can name them.
        """
        candidates = list(selectors)
        if not candidates:
            logger.debug("No selector candidates were given, so nothing was looked up.")
            return None

        actual_timeout = timeout if timeout is not None else self.config.short_timeout
        end_time = time.time() + actual_timeout

        while time.time() < end_time:
            for selector in candidates:
                if isinstance(selector, tuple):
                    curr_type, curr_sel = selector
                else:
                    curr_type, curr_sel = selector_type, selector

                try:
                    elements = self.driver.find_elements(curr_type, curr_sel)
                    for element in elements:
                        if element.is_displayed():
                            logger.debug("Selector matched: %s", curr_sel)
                            return element
                except (WebDriverException, ValueError, TypeError) as error:
                    logger.debug(
                        "Selector miss: %s %s (%s)", curr_type, curr_sel, error
                    )
                    continue
                logger.debug("Selector found nothing visible: %s", curr_sel)
            time.sleep(0.5)

        self.last_miss = SelectorMiss(
            candidates=tuple(selector_text(candidate) for candidate in candidates),
            page=self._current_page(),
            seconds=actual_timeout,
        )
        logger.warning(
            "No selector matched after %ss (%d candidates): %s on %s",
            actual_timeout,
            len(candidates),
            candidates,
            self.last_miss.page,
        )
        return None

    def _current_page(self) -> str:
        """Return the page URL for a log line, or a plain placeholder.

        WHY
          A missing selector is worth a log line even when the browser has
          already closed, which is exactly when the URL lookup fails.

        Returns
          str, the current URL, or "an unknown page" when it cannot be read.
        """
        try:
            return self.driver.current_url
        except WebDriverException:
            return "an unknown page"

    def click_with_fallback(self, element: WebElement, element_name: str) -> bool:
        """Attempt to click an element using progressively stronger fallbacks.

        WHY
          Native clicks often fail because of overlays or intercepts, so layering
          fallbacks improves the chance the control is pressed.

        Args
          element: WebElement, the target control from the caller.
          element_name: str, a friendly name for the log lines.

        Returns
          bool, True when any click strategy succeeded, False otherwise.

        MUTATIONS
          clicks the element when a strategy succeeds.
        """
        # Standard 3: Basic validation
        if not isinstance(element, WebElement):
            logger.error(f"Cannot click non-WebElement: {type(element)}")
            return False

        try:
            element.click()
            logger.info(f"Clicked '{element_name}' button normally")
            return True
        except WebDriverException:
            logger.info(
                f"Click '{element_name}' intercepted, trying JavaScript fallback"
            )
            try:
                self.driver.execute_script("arguments[0].click();", element)
                logger.info(f"Clicked '{element_name}' button using JavaScript")
                return True
            except WebDriverException:
                logger.info(
                    f"JavaScript click failed for '{element_name}', trying ActionChains"
                )
                try:
                    actions = ActionChains(self.driver)
                    actions.move_to_element(element).click().perform()
                    logger.info(f"Clicked '{element_name}' button using ActionChains")
                    return True
                except WebDriverException as ac_e:
                    logger.error(
                        f"All click methods failed for '{element_name}': "
                        f"{_error_summary(ac_e)}"
                    )
                    logger.debug("Click failure detail", exc_info=True)
                    return False

    def caret_to_end(self, contenteditable_element: WebElement) -> bool:
        """Position the cursor at the end of a contenteditable region.

        WHY
          Put later typing or mention insertion at the tail of the existing
          text, and report False when the element is not a WebElement.

        Args
          contenteditable_element: WebElement, the editor from the caller.

        Returns
          bool, True when cursor placement appears to work, False otherwise.

        MUTATIONS
          moves the selection and focus inside the editor.
        """
        # Standard 3: Basic validation
        if not isinstance(contenteditable_element, WebElement):
            return False

        try:
            js = """
                const el = arguments[0];
                if (!el) return false;
                try {
                  const range = document.createRange();
                  range.selectNodeContents(el);
                  range.collapse(false);
                  const sel = window.getSelection();
                  sel.removeAllRanges();
                  sel.addRange(range);
                  return true;
                } catch (e) {
                  try { el.focus && el.focus(); } catch(e2){}
                  return false;
                }
            """
            ok = self.driver.execute_script(js, contenteditable_element)
            if ok:
                logger.info("CARET moved_to_end via JS range")
                return True
        except WebDriverException:
            pass
        # Fallback: try focusing element and sending End key
        try:
            try:
                contenteditable_element.click()
            except WebDriverException:
                self.click_with_fallback(
                    contenteditable_element, "contenteditable focus (caret)"
                )
            actions = ActionChains(self.driver)
            actions.send_keys(Keys.END).perform()
            logger.info("CARET moved_to_end via Keys.END fallback")
            return True
        except WebDriverException as e:
            logger.debug(f"CARET move_to_end failed: {e.msg}")
            return False

    def caret_to_start(self, contenteditable_element: WebElement) -> bool:
        """Position the cursor at the start of a contenteditable region.

        WHY
          Place mentions at the beginning of the editor, such as AI comments
          that prepend an author mention.

        Args
          contenteditable_element: WebElement, the editor from the caller.

        Returns
          bool, True when cursor placement appears to work, False otherwise.

        MUTATIONS
          moves the selection and focus inside the editor.
        """
        # Standard 3: Basic validation
        if not isinstance(contenteditable_element, WebElement):
            return False

        try:
            js = """
                const el = arguments[0];
                if (!el) return false;
                try {
                  const range = document.createRange();
                  range.selectNodeContents(el);
                  range.collapse(true);
                  const sel = window.getSelection();
                  sel.removeAllRanges();
                  sel.addRange(range);
                  return true;
                } catch (e) {
                  try { el.focus && el.focus(); } catch(e2){}
                  return false;
                }
            """
            ok = self.driver.execute_script(js, contenteditable_element)
            if ok:
                logger.info("CARET moved_to_start via JS range")
                return True
        except WebDriverException:
            pass
        # Fallback: try focusing element and sending Home key
        try:
            try:
                contenteditable_element.click()
            except WebDriverException:
                self.click_with_fallback(
                    contenteditable_element, "contenteditable focus (caret-start)"
                )
            actions = ActionChains(self.driver)
            actions.send_keys(Keys.HOME).perform()
            logger.info("CARET moved_to_start via Keys.HOME fallback")
            return True
        except WebDriverException as e:
            logger.debug(f"CARET move_to_start failed: {e.msg}")
            return False
