"""Insert real mention entities through LinkedIn's typeahead popover.

WHY
  Turn an "@name" request into a clickable entity, so posts and comments do
  not end up with raw text instead of a mention.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Iterable, Optional

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement

from laf.selectors.mentions import MentionSelectors

from ..ui import UiActions
from .overlays import OverlayService

logger = logging.getLogger(__name__)

class MentionService:
    """Insert mention entities into the composer or a comment editor.

    WHY
      Give the composer, feed and engage flows one reliable way to add a real
      mention instead of typing an "@" that stays plain text.
    """

    def __init__(self, ui: UiActions, overlays: OverlayService) -> None:
        """
        WHY
          Give mention insertion the driver, pacing helpers and the overlay
          cleanup it needs so the typeahead popover can be reached reliably.

        Args
          ui: UiActions, the shared Selenium action helper.
          overlays: OverlayService, used to hide the global search popover.

        MUTATIONS
          Stores the driver helper, the overlay service and the config on the
          instance.
        """
        self.ui = ui
        self.overlays = overlays
        self.config = ui.config

    def sanitize_bmp(self, text: str) -> str:
        """Keep only the characters the mention popover handles well.

        WHY
          LinkedIn's typeahead can mishandle characters above the Basic
          Multilingual Plane, so dropping them avoids a broken mention.

        Args
          text: str, the candidate name before it is typed.

        Returns
          str, the text with non-BMP characters removed, "" for None, and the
          original text when conversion or filtering fails.
        """
        # Standard 3: Basic validation
        if text is None:
            return ""
        if not isinstance(text, str):
            text = str(text)

        try:
            return "".join(ch for ch in text if ord(ch) <= 0xFFFF)
        except TypeError:
            return text

    def post_text_contains_inline_mentions(self, post_text: str) -> bool:
        """Tell whether the text holds an inline @{Name} token.

        WHY
          The composer types plain text differently from text with mention
          tokens, so it needs to know which path to take.

        Args
          post_text: str, the post or comment text to inspect.

        Returns
          bool, True when at least one @{...} token is present, False for empty
          or non-string input.
        """
        # Standard 3: Basic validation
        if not post_text or not isinstance(post_text, str):
            return False
        return bool(re.search(r"@\{[^}]+\}", post_text))

    def compose_text_with_mentions(self, post_area: WebElement, post_text: str) -> bool:
        """Type post text, turning each @{Name} token into a real mention.

        WHY
          Let an author write mentions inline in the post body without typing
          them into the popover by hand.

        Args
          post_area: WebElement, the editor to type into.
          post_text: str, the content with zero or more @{Name} tokens.

        Returns
          bool, True when all text was written, False when typing a segment
          failed or post_area is not a WebElement.

        MUTATIONS
          Types the text and mention entities into post_area.
        """
        # Standard 3: Basic validation
        if not isinstance(post_area, WebElement):
            logger.error(f"Cannot compose text on non-WebElement: {type(post_area)}")
            return False
        if not post_text:
            return True

        pattern = re.compile(r"@\{([^}]+)\}")
        idx = 0
        for match in pattern.finditer(post_text):
            segment = post_text[idx : match.start()]
            if segment:
                try:
                    post_area.send_keys(segment)
                except WebDriverException as e:
                    logger.info(f"Typing text segment failed: {e.msg}")
                    return False
                self.ui.pause(0.1, 0.3)

            name = match.group(1).strip()
            if name:
                try:
                    self.insert_mentions(post_area, [name], leading_space=False)
                except WebDriverException as e:
                    logger.info(f"Inline mention failed for '{name}': {e.msg}")
                    try:
                        post_area.send_keys(f"@{name}")
                    except WebDriverException:
                        return False
                self.ui.pause(0.1, 0.3)
            idx = match.end()

        tail = post_text[idx:]
        if tail:
            try:
                post_area.send_keys(tail)
            except WebDriverException as e:
                logger.info(f"Typing trailing text failed: {e.msg}")
                return False
        return True

    def insert_mentions(
        self,
        post_area: WebElement,
        names: Iterable[str],
        leading_space: bool = True,
        force_end: bool = False,
        force_start: bool = False,
    ) -> None:
        """Type each name into the editor and pick it from the popover.

        WHY
          Add real mention entities to a post or comment so the names link to
          their profiles instead of staying plain text.

        Args
          post_area: WebElement, the editor to type into.
          names: Iterable[str], the display names to mention.
          leading_space: bool, True to put a space before the "@".
          force_end: bool, True to move the caret to the end first.
          force_start: bool, True to move the caret to the start first.

        MUTATIONS
          Types the "@name" text and entities into post_area and may move its
          caret.
        """
        # Standard 3: Basic validation
        if not isinstance(post_area, WebElement):
            logger.error(f"Expected WebElement for post_area, got {type(post_area)}")
            return
        if not names:
            return

        try:
            self.ui.click_with_fallback(post_area, "post editor (before mentions)")
            self.ui.pause(0.3, 0.7)
        except WebDriverException:
            pass
        # Ensure caret at end if requested
        if force_start:
            try:
                self.ui.caret_to_start(post_area)
                self.ui.pause(0.1, 0.2)
            except WebDriverException:
                pass
        if force_end:
            try:
                self.ui.caret_to_end(post_area)
                self.ui.pause(0.1, 0.2)
            except WebDriverException:
                pass
        try:
            self.overlays.dismiss_global_search_overlay()
        except WebDriverException:
            pass

        for name in names:
            try:
                # Ensure separation before '@' so tray appears reliably
                need_space = True
                try:
                    last_char = (
                        self.ui.driver.execute_script(
                            "return (arguments[0].innerText||'').slice(-1);",
                            post_area,
                        )
                        or ""
                    )
                    need_space = leading_space or (
                        not last_char or (isinstance(last_char, str) and not last_char.isspace())
                    )
                except WebDriverException:
                    need_space = True
                if need_space:
                    try:
                        post_area.send_keys(" ")
                        self.ui.pause(
                            self.config.min_typing_delay, self.config.max_typing_delay
                        )
                    except WebDriverException:
                        pass
                post_area.send_keys("@")
                self.ui.pause(0.2, 0.5)
                try:
                    if self.config.capture_typeahead_html:
                        self._capture_typeahead_snapshot(name)
                except WebDriverException:
                    pass
                safe_name = self.sanitize_bmp(name)
                for ch in safe_name:
                    post_area.send_keys(ch)
                    self.ui.pause(self.config.min_typing_delay, self.config.max_typing_delay)
                # Nudge the editor to reliably trigger LinkedIn's typeahead:
                # add a space, then backspace to return caret to the name end
                try:
                    logger.info("MENTIONS_NUDGE space+backspace applied")
                    post_area.send_keys(" ")
                    self.ui.pause(0.1, 0.25)
                    post_area.send_keys(Keys.BACKSPACE)
                except WebDriverException:
                    pass
                try:
                    if self.config.capture_typeahead_html:
                        self._capture_typeahead_snapshot(name)
                except WebDriverException:
                    pass
                # Give the suggestions tray more time to populate
                self.ui.pause(1.5, 2.5)
                self._wait_for_mention_suggestions(name, timeout=8)

                # Selection strategy: prefer the first visible suggestion after a short wait
                # (per requested behavior). Fallback to best textual match if needed.
                selected = self._select_first_mention_suggestion(
                    post_area, expected_name=None, prefer_first=True
                )
                if not selected:
                    selected = self._select_first_mention_suggestion(
                        post_area, expected_name=safe_name, prefer_first=False
                    )
                logger.info(f"MENTIONS_SELECT prefer_first={'yes'} selected={bool(selected)}")

                # Verify mention entity; do not try again to avoid duplicates
                self.verify_mention_entity(post_area, name, timeout=4)
                # Always add a trailing space after the mention so the next word doesn't stick
                try:
                    post_area.send_keys(" ")
                except WebDriverException:
                    pass

                try:
                    self._cleanup_trailing_newline(post_area)
                except WebDriverException:
                    pass
            except WebDriverException as e:
                logger.info(f"Mention insertion fallback for '{name}': {e.msg}")

    def _cleanup_trailing_newline(self, post_area: WebElement, attempts: int = 2) -> None:
        """Remove a trailing newline that a mention selection left behind.

        WHY
          LinkedIn sometimes adds a newline after a mention, which breaks the
          look of the paragraph that follows.

        Args
          post_area: WebElement, the editor to clean.
          attempts: int, the most backspaces to send, defaulting to 2.

        MUTATIONS
          Sends backspaces into post_area.
        """
        # Standard 3: Basic validation
        if not isinstance(post_area, WebElement):
            return

        try:
            for _ in range(max(1, attempts)):
                txt = (
                    self.ui.driver.execute_script(
                        "return (arguments[0].innerText||'').toString();", post_area
                    )
                    or ""
                )

                if not txt or not txt.endswith("\n"):
                    break
                post_area.send_keys(Keys.BACKSPACE)
                self.ui.pause(0.05, 0.15)
        except WebDriverException:
            pass

    def _wait_for_mention_suggestions(
        self, expected_text: str, timeout: Optional[float] = None
    ) -> bool:
        """Wait for the mention popover to show at least one visible item.

        WHY
          Selecting a suggestion only works once the tray has filled, so the
          caller needs to know when that happened.

        Args
          expected_text: str, the name that was typed, used for the diagnostics.
          timeout: Optional[float], the most seconds to wait, or None to use the
            config short timeout.

        Returns
          bool, True when a visible suggestion appeared, False when the wait ran
          out or expected_text was empty.
        """
        # Standard 3: Basic validation
        if not expected_text:
            return False

        actual_timeout = timeout if timeout is not None else self.config.short_timeout
        selectors = MentionSelectors.SUGGESTIONS
        end_time = time.time() + actual_timeout
        while time.time() < end_time:
            for sel in selectors:
                try:
                    items = self.ui.driver.find_elements(By.XPATH, sel)
                    visible = [i for i in items if i.is_displayed()]
                    if visible:
                        logger.info(
                            f"Detected {len(visible)} mention suggestion items "
                            f"via selector: {sel}"
                        )
                        try:
                            if self.config.capture_typeahead_html:
                                self._capture_typeahead_snapshot(expected_text)
                        except WebDriverException as cap_e:
                            logger.debug(f"Typeahead snapshot capture skipped: {cap_e}")
                        return True
                except WebDriverException:
                    continue
            time.sleep(0.2)
        return False

    def _capture_typeahead_snapshot(self, typed_text: Optional[str] = None) -> None:
        """Save the current mention popover HTML and items to files.

        WHY
          A later mention regression is easier to debug when the actual popover
          markup from the failing run is on disk.

        Args
          typed_text: Optional[str], the name that was typed, used in the file
            names, or None.

        MUTATIONS
          Writes an .html and a .json snapshot into the configured capture
          directory.
        """
        try:
            capture_dir = Path(self.config.typeahead_capture_dir)
            capture_dir.mkdir(parents=True, exist_ok=True)
            container_xpaths = MentionSelectors.TYPEAHEAD_CONTAINERS
            container = None
            for xp in container_xpaths:
                try:
                    el = self.ui.driver.find_element(By.XPATH, xp)
                    if el and el.is_displayed():
                        container = el
                        break
                except WebDriverException:
                    continue
            if not container:
                logger.debug("Typeahead capture: no container found")
                return
            js = (
                """
                const root = arguments[0];
                const html = root ? root.outerHTML : '';
                const items = [];
                if (root) {
                  const nodes = root.querySelectorAll('li, button, a, div');
                  for (const n of nodes) {
                    if (!n.offsetParent) continue;
                    const txt = (n.innerText || n.textContent || '').trim();
                    if (!txt) continue;
                    const cls = (n.className || '').toString();
                    const href = n.getAttribute && n.getAttribute('href');
                    const urn = n.getAttribute && (n.getAttribute('data-entity-urn') """
                "|| n.getAttribute('data-urn'));\n"
                "                    items.push({text: txt, className: cls, "
                "href: href || null, urn: urn || null});\n"
                """                  }
                }
                return { html, items };
            """
            )
            res = self.ui.driver.execute_script(js, container) or {}
            outer_html = res.get("html", "")
            items = res.get("items", [])
            ts = time.strftime("%Y%m%d_%H%M%S")
            base = f"typeahead_{ts}"
            if typed_text:
                safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(typed_text))[:40]
                if safe:
                    base += f"_{safe}"
            html_path = capture_dir / f"{base}.html"
            json_path = capture_dir / f"{base}.json"
            try:
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(outer_html)
            except OSError as e:
                logger.debug(f"Failed writing HTML snapshot: {e}")
            try:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "typed": typed_text,
                            "captured_at": ts,
                            "container": "editor-typeahead-fetch or similar",
                            "items": items,
                        },
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
            except (OSError, TypeError, ValueError) as e:
                logger.debug(f"Failed writing JSON snapshot: {e}")
            logger.info(f"Saved typeahead snapshot to {html_path} and {json_path}")
        except (OSError, WebDriverException) as e:
            logger.debug(f"Typeahead capture error: {e}")

    def verify_mention_entity(
        self, post_area: WebElement, name: str, timeout: Optional[float] = None
    ) -> bool:
        """Check that a selected mention rendered as a LinkedIn entity.

        WHY
          Catch the case where the popover failed and the editor still holds
          raw "@name" text, so the caller can log or fall back.

        Args
          post_area: WebElement, the editor that should hold the mention.
          name: str, the display name that was selected.
          timeout: Optional[float], the most seconds to poll, or None to use the
            config short timeout.

        Returns
          bool, True when a mention entity is found, False when the wait ran out
          or name was empty.
        """
        # Standard 3: Basic validation
        if not isinstance(post_area, WebElement):
            return False

        actual_timeout = timeout if timeout is not None else self.config.short_timeout
        end_time = time.time() + actual_timeout
        safe_name = (name or "").strip()
        if not safe_name:
            return False
        xpath_templates = MentionSelectors.ENTITY_TEMPLATES
        while time.time() < end_time:
            for tpl in xpath_templates:
                xp = tpl.format(t=safe_name)
                try:
                    el = post_area.find_element(By.XPATH, xp)
                    if el and el.is_displayed():
                        return True
                except WebDriverException:
                    continue
            try:
                js = (
                    """
                    const root = arguments[0];
                    const name = (arguments[1]||'').toLowerCase();
                    if (!root) return false;
                    const nodes = root.querySelectorAll('a, span, strong, em');
                    for (const n of nodes) {
                        const cls = (n.className || '').toLowerCase();
                        const txt = (n.innerText || n.textContent || '').trim().toLowerCase();
                        if ((cls.includes('mention') || cls.includes('ql-mention') """
                    "|| cls.includes('entity')) && txt.includes(name)) {\n"
                    """                            return true;
                        }
                    }
                    return false;
                """
                )
                ok = self.ui.driver.execute_script(js, post_area, safe_name)
                if ok:
                    return True
            except WebDriverException:
                pass
            time.sleep(0.2)
        return False

    def _select_first_mention_suggestion(
        self, post_area: WebElement, expected_name: Optional[str] = None, prefer_first: bool = False
    ) -> bool:
        """Click either the first suggestion or the best name match.

        WHY
          Pick a mention from the tray so the raw "@name" text becomes an
          entity, even when the first suggestion is not the wanted person.

        Args
          post_area: WebElement, the editor, used only for the type check.
          expected_name: Optional[str], the name to favour when scoring, or None.
          prefer_first: bool, True to take the first visible suggestion.

        Returns
          bool, True when a suggestion was clicked, False when none was visible
          or every click failed.
        """
        # Standard 3: Basic validation
        if not isinstance(post_area, WebElement):
            return False

        # Prefer clicking the first visible suggestion inside the tray
        if prefer_first:
            try:
                for xp in MentionSelectors.SUGGESTIONS:
                    try:
                        elements = self.ui.driver.find_elements(By.XPATH, xp)
                        for el in elements:
                            if el.is_displayed():
                                try:
                                    self.ui.driver.execute_script(
                                        "arguments[0].scrollIntoView({block:'center'});", el
                                    )
                                except WebDriverException:
                                    pass
                                try:
                                    el.click()
                                except WebDriverException:
                                    self.ui.driver.execute_script("arguments[0].click();", el)
                                self.ui.pause(0.2, 0.4)
                                return True
                    except WebDriverException:
                        continue
            except WebDriverException:
                pass

        # Fallback: click best textual match
        item_selectors = MentionSelectors.FALLBACK_SUGGESTIONS
        for sel in item_selectors:
            try:
                items = self.ui.driver.find_elements(By.XPATH, sel)

                def score(el: WebElement) -> int:
                    """Rank one suggestion by how well its text matches the name.

                    WHY
                      A higher score puts the closest person first, so the click
                      lands on the intended mention.

                    Args
                      el: WebElement, one suggestion from the tray.

                    Returns
                      int, 3 for an exact match, 2 for a prefix, 1 for a
                      substring, and 0 otherwise or on error.
                    """
                    try:
                        t = (el.text or "").strip().lower()
                        exp = (expected_name or "").strip().lower()
                        if not exp:
                            return 0
                        if t == exp:
                            return 3
                        if t.startswith(exp):
                            return 2
                        if exp in t:
                            return 1
                        return 0
                    except WebDriverException:
                        return 0

                ranked = sorted(items, key=score, reverse=True) if items else []
                for el in ranked or items:
                    if not el.is_displayed():
                        continue
                    try:
                        self.ui.driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});", el
                        )
                    except WebDriverException:
                        pass
                    try:
                        el.click()
                        self.ui.pause(0.2, 0.5)
                        return True
                    except WebDriverException:
                        try:
                            self.ui.driver.execute_script("arguments[0].click();", el)
                            self.ui.pause(0.2, 0.5)
                            return True
                        except WebDriverException:
                            continue
            except WebDriverException:
                continue

        # Keyboard fallback: press DOWN + ENTER to accept the first suggestion.
        # Bypasses CSS selectors entirely — uses LinkedIn's native keyboard nav.
        try:
            post_area.send_keys(Keys.ARROW_DOWN)
            self.ui.pause(0.1, 0.2)
            post_area.send_keys(Keys.ENTER)
            self.ui.pause(0.2, 0.4)
            logger.info("MENTIONS_SELECT keyboard_fallback selected=True")
            return True
        except WebDriverException as e:
            logger.info(f"MENTIONS_SELECT keyboard_fallback failed: {e.msg}")

        return False
