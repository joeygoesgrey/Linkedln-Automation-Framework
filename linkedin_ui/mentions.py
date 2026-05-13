"""Mention insertion helpers for LinkedIn's composer popover.

Why:
    Decouple brittle mention behaviour from the rest of the posting workflow.

When:
    Mixed into :class:`LinkedInInteraction` whenever inline placeholders or
    explicit mention requests need to resolve to LinkedIn entities.

How:
    Types ``@`` sequences with human-like delays, waits for the popover,
    optionally captures diagnostics, selects the best suggestion, and verifies
    entity insertion.
"""

import re
import time
import json
import logging
from pathlib import Path
from typing import Optional, List, Iterable, Any
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement

import config
from ui_selectors import MentionSelectors


class MentionsMixin:
    """Provide resilient mention insertion utilities for the composer/editor.

    Why:
        Centralise brittle mention logic so higher-level code remains concise.

    When:
        Mixed into :class:`LinkedInInteraction` whenever posts or comments need mentions.

    How:
        Offers helpers for sanitising names, detecting placeholders, inserting mentions, and verifying entities.
    """
    def _sanitize_bmp(self, text: str) -> str:
        """Remove non-BMP characters to keep typeahead input stable.

        Why:
            LinkedIn's mention popover can mis-handle characters beyond the
            Basic Multilingual Plane; filtering them reduces risk.

        When:
            Right before simulating keystrokes for mention names.

        How:
            Iterates characters and retains only those with code points <= 0xFFFF.

        Args:
            text (str): Candidate string.

        Returns:
            str: Sanitised string safe for editor input.
        """
        # Standard 3: Basic validation
        if text is None:
            return ""
        if not isinstance(text, str):
            text = str(text)

        try:
            return "".join(ch for ch in text if ord(ch) <= 0xFFFF)
        except Exception:
            return text

    def _post_text_contains_inline_mentions(self, post_text: str) -> bool:
        """Detect ``@{Name}`` placeholders within supplied text.

        Why:
            Drives the decision to process inline mention tokens versus typing
            text verbatim.

        When:
            Checked prior to composing post or comment content.

        How:
            Uses a regex search for ``@{...}`` patterns.

        Args:
            post_text (str): Text to inspect.

        Returns:
            bool: ``True`` if placeholders exist, otherwise ``False``.
        """
        # Standard 3: Basic validation
        if not post_text or not isinstance(post_text, str):
            return False
        return bool(re.search(r"@\{[^}]+\}", post_text))

    def _compose_text_with_mentions(self, post_area: WebElement, post_text: str) -> bool:
        """Type text segments while resolving inline mention placeholders.

        Why:
            Authors can specify mentions inline using ``@{Name}`` tokens; this
            helper expands them into real entities.

        When:
            Called by posting/commenting flows when inline placeholders are
            detected.

        How:
            Splits the text by placeholder boundaries, types plain segments, and
            leverages :meth:`_insert_mentions` for each captured name.

        Args:
            post_area (WebElement): Editor element.
            post_text (str): Content with zero or more placeholders.

        Returns:
            bool: ``True`` when composition succeeds, otherwise ``False``.
        """
        # Standard 3: Basic validation
        if not isinstance(post_area, WebElement):
            logging.error(f"Cannot compose text on non-WebElement: {type(post_area)}")
            return False
        if not post_text:
            return True

        pattern = re.compile(r"@\{([^}]+)\}")
        idx = 0
        for match in pattern.finditer(post_text):
            segment = post_text[idx:match.start()]
            if segment:
                try:
                    post_area.send_keys(segment)
                except Exception as e:
                    logging.info(f"Typing text segment failed: {e}")
                    return False
                self.random_delay(0.1, 0.3)

            name = match.group(1).strip()
            if name:
                try:
                    self._insert_mentions(post_area, [name], leading_space=False)
                except Exception as e:
                    logging.info(f"Inline mention failed for '{name}': {e}")
                    try:
                        post_area.send_keys(f"@{name}")
                    except Exception:
                        return False
                self.random_delay(0.1, 0.3)
            idx = match.end()

        tail = post_text[idx:]
        if tail:
            try:
                post_area.send_keys(tail)
            except Exception as e:
                logging.info(f"Typing trailing text failed: {e}")
                return False
        return True

    def _insert_mentions(
        self,
        post_area: WebElement,
        names: Iterable[str],
        leading_space: bool = True,
        force_end: bool = False,
        force_start: bool = False,
    ) -> None:
        """Insert mention entities into the active editor.

        Why:
            Automating manual ``@`` typing improves reliability and enables
            scripting of complex mention scenarios.

        When:
            Triggered by inline placeholders or explicit mention arguments.

        How:
            Focuses the editor, optionally repositions the caret, types ``@``
            and the sanitised name with human delays, nudges the popover to
            refresh, waits for suggestions, selects a candidate, verifies the
            entity, and tidies whitespace.

        Args:
            post_area (WebElement): Editor element into which mentions are typed.
            names (Iterable[str]): Display names to mention.
            leading_space (bool): Whether to insert a space before ``@``.
            force_end (bool): Force caret to the end before insertion.
            force_start (bool): Force caret to the beginning before insertion.

        Returns:
            None
        """
        # Standard 3: Basic validation
        if not isinstance(post_area, WebElement):
            logging.error(f"Expected WebElement for post_area, got {type(post_area)}")
            return
        if not names:
            return

        try:
            self._click_element_with_fallback(post_area, "post editor (before mentions)")
            self.random_delay(0.3, 0.7)
        except Exception:
            pass
        # Ensure caret at end if requested
        if force_start:
            try:
                self._move_caret_to_start(post_area)
                self.random_delay(0.1, 0.2)
            except Exception:
                pass
        if force_end:
            try:
                self._move_caret_to_end(post_area)
                self.random_delay(0.1, 0.2)
            except Exception:
                pass
        try:
            self._dismiss_global_search_overlay()
        except Exception:
            pass

        for name in names:
            try:
                # Ensure separation before '@' so tray appears reliably
                need_space = True
                try:
                    last_char = self.driver.execute_script(
                        "return (arguments[0].innerText||'').slice(-1);",
                        post_area,
                    ) or ""
                    need_space = leading_space or (not last_char or (isinstance(last_char, str) and not last_char.isspace()))
                except Exception:
                    need_space = True
                if need_space:
                    try:
                        post_area.send_keys(" ")
                        self.random_delay(config.MIN_TYPING_DELAY, config.MAX_TYPING_DELAY)
                    except Exception:
                        pass
                post_area.send_keys("@")
                self.random_delay(0.2, 0.5)
                try:
                    if config.CAPTURE_TYPEAHEAD_HTML:
                        self._capture_typeahead_snapshot(name)
                except Exception:
                    pass
                safe_name = self._sanitize_bmp(name)
                for ch in safe_name:
                    post_area.send_keys(ch)
                    self.random_delay(config.MIN_TYPING_DELAY, config.MAX_TYPING_DELAY)
                # Nudge the editor to reliably trigger LinkedIn's typeahead:
                # add a space, then backspace to return caret to the name end
                try:
                    logging.info("MENTIONS_NUDGE space+backspace applied")
                    post_area.send_keys(" ")
                    self.random_delay(0.1, 0.25)
                    post_area.send_keys(Keys.BACKSPACE)
                except Exception:
                    pass
                try:
                    if config.CAPTURE_TYPEAHEAD_HTML:
                        self._capture_typeahead_snapshot(name)
                except Exception:
                    pass
                # Give the suggestions tray more time to populate
                self.random_delay(1.5, 2.5)
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
                try:
                    logging.info(f"MENTIONS_SELECT prefer_first={'yes'} selected={bool(selected)}")
                except Exception:
                    pass

                # Verify mention entity; do not try again to avoid duplicates
                self._verify_mention_entity(post_area, name, timeout=4)
                # Always add a trailing space after the mention so the next word doesn't stick
                try:
                    post_area.send_keys(" ")
                except Exception:
                    pass

                try:
                    self._cleanup_trailing_newline(post_area)
                except Exception:
                    pass
            except Exception as e:
                logging.info(f"Mention insertion fallback for '{name}': {e}")

    def _cleanup_trailing_newline(self, post_area: WebElement, attempts: int = 2) -> None:
        """Remove trailing newline characters introduced by mentions.

        Why:
            LinkedIn sometimes inserts newlines after selecting a mention; this
            keeps formatting tidy.

        When:
            Called after each mention insertion attempt.

        How:
            Reads the editor text via JavaScript and issues backspaces while the
            tail contains newline characters, up to ``attempts`` times.

        Args:
            post_area (WebElement): Editor under modification.
            attempts (int): Maximum number of cleanup iterations.

        Returns:
            None
        """
        # Standard 3: Basic validation
        if not isinstance(post_area, WebElement):
            return

        try:
            for _ in range(max(1, attempts)):
                txt = self.driver.execute_script(
                    "return (arguments[0].innerText||'').toString();", post_area
                ) or ""
           
                if not txt or not txt.endswith("\n"):
                    break
                post_area.send_keys(Keys.BACKSPACE)
                self.random_delay(0.05, 0.15)
        except Exception:
            pass

    def _wait_for_mention_suggestions(self, expected_text: str, timeout: Optional[float] = None) -> bool:
        """Wait until the mention suggestion tray displays visible entries.

        Why:
            Ensures subsequent selection logic interacts with a populated popover.

        When:
            Immediately after typing the mention name.

        How:
            Polls multiple XPath selectors for visible items until the timeout
            expires.

        Args:
            expected_text (str): The text typed into the mention popover.
            timeout (float | None): Maximum wait time in seconds.

        Returns:
            bool: ``True`` if suggestions appear, otherwise ``False``.
        """
        # Standard 3: Basic validation
        if not expected_text:
            return False

        actual_timeout = timeout if timeout is not None else config.SHORT_TIMEOUT
        selectors = MentionSelectors.SUGGESTIONS
        end_time = time.time() + actual_timeout
        while time.time() < end_time:
            for sel in selectors:
                try:
                    items = self.driver.find_elements(By.XPATH, sel)
                    visible = [i for i in items if i.is_displayed()]
                    if visible:
                        try:
                            logging.info(
                                f"Detected {len(visible)} mention suggestion items via selector: {sel}"
                            )
                        except Exception:
                            pass
                        try:
                            if config.CAPTURE_TYPEAHEAD_HTML:
                                self._capture_typeahead_snapshot(expected_text)
                        except Exception as cap_e:
                            logging.debug(f"Typeahead snapshot capture skipped: {cap_e}")
                        return True
                except Exception:
                    continue
            time.sleep(0.2)
        return False

    def _capture_typeahead_snapshot(self, typed_text: Optional[str] = None) -> None:
        """Persist the current typeahead DOM/metadata for diagnostics.

        Why:
            Debugging mention regressions benefits from captured HTML/JSON to
            compare against expected structures.

        When:
            Called opportunistically when ``CAPTURE_TYPEAHEAD_HTML`` is enabled.

        How:
            Locates the popover container, serialises its HTML and visible items
            via JavaScript, and writes timestamped files to the capture directory.

        Args:
            typed_text (str | None): Text typed into the popover, used for
                naming captured artifacts.

        Returns:
            None
        """
        try:
            capture_dir = Path(config.TYPEAHEAD_CAPTURE_DIR)
            capture_dir.mkdir(parents=True, exist_ok=True)
            container_xpaths = MentionSelectors.TYPEAHEAD_CONTAINERS
            container = None
            for xp in container_xpaths:
                try:
                    el = self.driver.find_element(By.XPATH, xp)
                    if el and el.is_displayed():
                        container = el
                        break
                except Exception:
                    continue
            if not container:
                logging.debug("Typeahead capture: no container found")
                return
            js = """
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
                    const urn = n.getAttribute && (n.getAttribute('data-entity-urn') || n.getAttribute('data-urn'));
                    items.push({text: txt, className: cls, href: href || null, urn: urn || null});
                  }
                }
                return { html, items };
            """
            res = self.driver.execute_script(js, container) or {}
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
            except Exception as e:
                logging.debug(f"Failed writing HTML snapshot: {e}")
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
            except Exception as e:
                logging.debug(f"Failed writing JSON snapshot: {e}")
            logging.info(f"Saved typeahead snapshot to {html_path} and {json_path}")
        except Exception as e:
            logging.debug(f"Typeahead capture error: {e}")

    def _verify_mention_entity(self, post_area: WebElement, name: str, timeout: Optional[float] = None) -> bool:
        """Confirm that a selected mention rendered as a LinkedIn entity.

        Why:
            Ensures automation does not leave raw ``@`` text when the popover
            fails to select an entity.

        When:
            Invoked immediately after attempting to pick a suggestion.

        How:
            Searches for mention-related classes in the DOM and, failing that,
            executes JavaScript scans to detect entity markers.

        Args:
            post_area (WebElement): Editor containing the mention.
            name (str): Expected mention display name.
            timeout (float | None): Seconds to poll for confirmation.

        Returns:
            bool: ``True`` when a mention entity is found, otherwise ``False``.
        """
        # Standard 3: Basic validation
        if not isinstance(post_area, WebElement):
            return False

        actual_timeout = timeout if timeout is not None else config.SHORT_TIMEOUT
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
                except Exception:
                    continue
            try:
                js = """
                    const root = arguments[0];
                    const name = (arguments[1]||'').toLowerCase();
                    if (!root) return false;
                    const nodes = root.querySelectorAll('a, span, strong, em');
                    for (const n of nodes) {
                        const cls = (n.className || '').toLowerCase();
                        const txt = (n.innerText || n.textContent || '').trim().toLowerCase();
                        if ((cls.includes('mention') || cls.includes('ql-mention') || cls.includes('entity')) && txt.includes(name)) {
                            return true;
                        }
                    }
                    return false;
                """
                ok = self.driver.execute_script(js, post_area, safe_name)
                if ok:
                    return True
            except Exception:
                pass
            time.sleep(0.2)
        return False

    def _select_first_mention_suggestion(
        self, 
        post_area: WebElement, 
        expected_name: Optional[str] = None, 
        prefer_first: bool = False
    ) -> bool:
        """Choose a mention suggestion and click it.

        Why:
            Abstracts the logic for selecting either the first visible entry or
            the best textual match from the suggestion list.

        When:
            Called once suggestions are confirmed to be visible.

        How:
            Optionally prefers the first suggestion, otherwise sorts candidates
            by similarity score before attempting to click via native or JS
            events.

        Args:
            post_area (WebElement): Editor element, used for context.
            expected_name (str | None): Name to favour when scoring candidates.
            prefer_first (bool): Whether to always pick the first suggestion.

        Returns:
            bool: ``True`` when a suggestion is clicked, otherwise ``False``.
        """
        # Standard 3: Basic validation
        if not isinstance(post_area, WebElement):
            return False

        # Prefer clicking the first visible suggestion inside the tray
        if prefer_first:
            try:
                for xp in MentionSelectors.SUGGESTIONS:
                    try:
                        elements = self.driver.find_elements(By.XPATH, xp)
                        for el in elements:
                            if el.is_displayed():
                                try:
                                    self.driver.execute_script(
                                        "arguments[0].scrollIntoView({block:'center'});", el
                                    )
                                except Exception:
                                    pass
                                try:
                                    el.click()
                                except Exception:
                                    self.driver.execute_script("arguments[0].click();", el)
                                self.random_delay(0.2, 0.4)
                                return True
                    except Exception:
                        continue
            except Exception:
                pass

        # Fallback: click best textual match
        item_selectors = MentionSelectors.FALLBACK_SUGGESTIONS
        for sel in item_selectors:
            try:
                items = self.driver.find_elements(By.XPATH, sel)
                def score(el: WebElement) -> int:
                    """Compute a ranking score comparing a suggestion to the expected name.

                    Why:
                        Ensures the automation selects the closest textual match when not preferring the first result.

                    When:
                        Called while sorting suggestion elements prior to clicking.

                    How:
                        Normalises text to lowercase and assigns higher scores for exact matches, prefixes, and substring matches.

                    Args:
                        el (WebElement): Suggestion element to evaluate.

                    Returns:
                        int: Priority score (higher is better).
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
                    except Exception:
                        return 0
                ranked = sorted(items, key=score, reverse=True) if items else []
                for el in ranked or items:
                    if not el.is_displayed():
                        continue
                    try:
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});", el
                        )
                    except Exception:
                        pass
                    try:
                        el.click()
                        self.random_delay(0.2, 0.5)
                        return True
                    except Exception:
                        try:
                            self.driver.execute_script("arguments[0].click();", el)
                            self.random_delay(0.2, 0.5)
                            return True
                        except Exception:
                            continue
            except Exception:
                continue
        return False
