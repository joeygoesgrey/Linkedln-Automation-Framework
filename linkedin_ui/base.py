"""Shared Selenium helpers used across LinkedIn UI mixins.

Why:
    Keep common utilities (delays, element lookup, resilient clicking) in one
    place to avoid duplication across mixins.

When:
    Imported and mixed into :class:`LinkedInInteraction` prior to performing UI
    automation.

How:
    Provides small methods that operate on ``self.driver`` using configuration
    values to mimic human behaviour and handle UI quirks.
"""

import time
import random
import logging
from typing import Optional, Iterable, Union, Any
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

import config


class BaseInteraction:
    """Provide reusable Selenium utilities for LinkedIn automation mixins.

    Why:
        Avoid duplicating common patterns like waits, humanised typing, and
        click fallbacks.

    When:
        Mixed into :class:`LinkedInInteraction` and available to every feature
        mixin (login, composer, mentions, etc.).

    How:
        Stores the driver reference and exposes helper methods consumed by
        specialised mixins.
    """

    def __init__(self, driver: WebDriver) -> None:
        """Store the Selenium driver used by downstream mixins.

        Why:
            All helper methods require access to the underlying WebDriver.

        When:
            Called during construction of :class:`LinkedInInteraction`.

        How:
            Assigns ``driver`` to an instance attribute for later use.

        Args:
            driver (WebDriver): Active Selenium WebDriver.
        """
        # Standard 3: Basic validation
        if driver is None:
            raise ValueError("BaseInteraction requires a valid WebDriver instance.")
        self.driver = driver

    def random_delay(self, min_delay: Optional[float] = None, max_delay: Optional[float] = None) -> None:
        """Pause execution for a random interval within human bounds.

        Why:
            Mimic natural behaviour to reduce bot detection risk.

        When:
            Sprinkle throughout UI interactions between actions.

        How:
            Picks min/max defaults from config when absent and sleeps for a
            uniform random duration.

        Args:
            min_delay (float | None): Minimum seconds to sleep.
            max_delay (float | None): Maximum seconds to sleep.

        Returns:
            None
        """
        # Standard 3: Basic validation
        actual_min = min_delay if min_delay is not None else config.MIN_ACTION_DELAY
        actual_max = max_delay if max_delay is not None else config.MAX_ACTION_DELAY
        
        if actual_min < 0 or actual_max < 0:
            logging.warning(f"Negative delay requested: min={actual_min}, max={actual_max}. Defaulting to 0.")
            actual_min, actual_max = max(0, actual_min), max(0, actual_max)

        time.sleep(random.uniform(actual_min, actual_max))

    def _type_with_human_delays(self, element: WebElement, text: str) -> None:
        """Send text to a DOM element character-by-character with delays.

        Why:
            Emulates human typing to avoid triggering LinkedIn's bot heuristics.

        When:
            Used whenever text needs to be entered into contenteditable or input
            fields.

        How:
            Iterates over characters, calls ``send_keys`` on the element, and
            sleeps briefly between keystrokes.

        Args:
            element (WebElement): Target element to receive text.
            text (str): Content to type.

        Returns:
            None
        """
        # Standard 3: Basic validation
        if not isinstance(element, WebElement):
            raise TypeError(f"Expected WebElement, got {type(element)}")
        if not isinstance(text, str):
            text = str(text)

        for ch in text:
            element.send_keys(ch)
            self.random_delay(config.MIN_TYPING_DELAY, config.MAX_TYPING_DELAY)

    def _find_element_from_selectors(
        self, 
        selectors: Iterable[Union[str, tuple]], 
        selector_type: str, 
        timeout: Optional[float] = None
    ) -> Optional[WebElement]:
        """Locate an element by iterating through multiple selector options.

        Why:
            LinkedIn frequently tweaks DOM structure; cycling selectors adds
            resilience.

        When:
            Called by mixins when a single selector may not be stable.

        How:
            Attempts each selector with a WebDriverWait until one succeeds or
            the list is exhausted.

        Args:
            selectors (Iterable[str | tuple]): Candidate locator strings or (By, str) tuples.
            selector_type (str): Selenium locator strategy (e.g., By.CSS_SELECTOR).
            timeout (float | None): Optional timeout override in seconds.

        Returns:
            WebElement | None: Element if found, otherwise ``None``.
        """
        # Standard 3: Basic validation
        if not selectors:
            return None

        actual_timeout = timeout if timeout is not None else config.SHORT_TIMEOUT
        end_time = time.time() + actual_timeout
        
        while time.time() < end_time:
            for selector in selectors:
                try:
                    if isinstance(selector, tuple):
                        curr_type, curr_sel = selector
                    else:
                        curr_type, curr_sel = selector_type, selector
                        
                    elements = self.driver.find_elements(curr_type, curr_sel)
                    for el in elements:
                        if el.is_displayed():
                            return el
                except Exception:
                    continue
            time.sleep(0.5)
        return None

    def _click_element_with_fallback(self, element: WebElement, element_name: str) -> bool:
        """Attempt to click an element using progressively stronger fallbacks.

        Why:
            Native clicks often fail due to overlays or intercepts; layered
            fallbacks improve success.

        When:
            Before interacting with critical controls (post, comment, etc.).

        How:
            Tries native ``click()``, JavaScript execution, then ActionChains.

        Args:
            element (WebElement): Target element to click.
            element_name (str): Friendly name for logging context.

        Returns:
            bool: ``True`` if any strategy succeeds, otherwise ``False``.
        """
        # Standard 3: Basic validation
        if not isinstance(element, WebElement):
            logging.error(f"Cannot click non-WebElement: {type(element)}")
            return False

        try:
            element.click()
            logging.info(f"Clicked '{element_name}' button normally")
            return True
        except Exception as e:
            logging.info(f"Standard click failed, trying JavaScript: {e}")
            try:
                self.driver.execute_script("arguments[0].click();", element)
                logging.info(f"Clicked '{element_name}' button using JavaScript")
                return True
            except Exception as js_e:
                logging.info(f"JavaScript click failed, trying ActionChains: {js_e}")
                try:
                    actions = ActionChains(self.driver)
                    actions.move_to_element(element).click().perform()
                    logging.info(f"Clicked '{element_name}' button using ActionChains")
                    return True
                except Exception as ac_e:
                    logging.error(f"All click methods failed for '{element_name}': {ac_e}")
                    return False

    def _move_caret_to_end(self, contenteditable_element: WebElement) -> bool:
        """Position the cursor at the end of a contenteditable region.

        Why:
            Ensures subsequent typing or mention insertion occurs at the tail of
            the existing text.

        When:
            Used prior to appending content or mentions.

        How:
            Attempts a JavaScript range selection and falls back to sending the
            End key via ActionChains.

        Args:
            contenteditable_element (WebElement): Editor element to manipulate.

        Returns:
            bool: ``True`` when cursor placement appears successful, else ``False``.
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
                logging.info("CARET moved_to_end via JS range")
                return True
        except Exception:
            pass
        # Fallback: try focusing element and sending End key
        try:
            try:
                contenteditable_element.click()
            except Exception:
                self._click_element_with_fallback(contenteditable_element, "contenteditable focus (caret)")
            actions = ActionChains(self.driver)
            actions.send_keys(Keys.END).perform()
            logging.info("CARET moved_to_end via Keys.END fallback")
            return True
        except Exception as e:
            logging.debug(f"CARET move_to_end failed: {e}")
            return False

    def _move_caret_to_start(self, contenteditable_element: WebElement) -> bool:
        """Position the cursor at the start of a contenteditable region.

        Why:
            Required when mentions must be inserted at the beginning of the
            editor (e.g., AI comments that prepend author mentions).

        When:
            Called before inserting mentions with ``force_start=True``.

        How:
            Attempts a collapsed JavaScript range and falls back to sending the
            Home key via ActionChains.

        Args:
            contenteditable_element (WebElement): Editor element to manipulate.

        Returns:
            bool: ``True`` when cursor placement appears successful, else ``False``.
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
                logging.info("CARET moved_to_start via JS range")
                return True
        except Exception:
            pass
        # Fallback: try focusing element and sending Home key
        try:
            try:
                contenteditable_element.click()
            except Exception:
                self._click_element_with_fallback(contenteditable_element, "contenteditable focus (caret-start)")
            actions = ActionChains(self.driver)
            actions.send_keys(Keys.HOME).perform()
            logging.info("CARET moved_to_start via Keys.HOME fallback")
            return True
        except Exception as e:
            logging.debug(f"CARET move_to_start failed: {e}")
            return False
