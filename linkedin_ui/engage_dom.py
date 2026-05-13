"""DOM traversal and interaction helpers supporting the engage stream.

Why:
    Break down low-level DOM operations so higher-level flow code remains
    focused on business logic.

When:
    Mixed into :class:`LinkedInInteraction` for engage-stream runs.

How:
    Provides utilities for author extraction, deduplication keys, scrolling,
    text harvesting, and comment/like actions at the DOM level.
"""

from __future__ import annotations

import json
import logging
import random
import time
import hashlib
import re
from pathlib import Path
from typing import Optional, List, Dict

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import config
from ui_selectors import EngageSelectors


class EngageDomMixin:
    """Provides DOM traversal, extraction, and interaction helpers."""

    # ------------------------------------------------------------------
    # Author extraction utilities

    def _extract_author_name(self, root) -> Optional[str]:
        """Best-effort extraction of the post author's display name.

        Why:
            Author names are used for mention placement, deduping, and logging.

        When:
            Called whenever engage logic processes a visible post root.

        How:
            Attempts multiple XPath selectors, falls back to aria-label parsing,
            and normalises the result.

        Args:
            root (WebElement): Post container element.

        Returns:
            str | None: Normalised author name or ``None`` if detection fails.
        """
        if root is None:
            return None

        selectors = EngageSelectors.AUTHOR_NAME

        for xp in selectors:
            try:
                for node in root.find_elements(By.XPATH, xp):
                    if not node.is_displayed():
                        continue
                    candidate = self._normalize_person_name(node.text)
                    if candidate:
                        return candidate
            except Exception:
                continue

        # Fallback: parse aria-label fragments like "Post by Jane Doe"
        try:
            aria = (root.get_attribute("aria-label") or "").strip()
            if aria:
                for marker in ("by ", "for "):
                    if marker in aria:
                        fragment = aria.split(marker, 1)[1].strip()
                        fragment = re.split(r"[|•·\-–—]|\s{2,}", fragment)[0].strip()
                        candidate = self._normalize_person_name(fragment)
                        if candidate:
                            return candidate
        except Exception:
            pass

        return None

    def _normalize_person_name(self, name: str) -> str:
        """Normalise LinkedIn name strings by trimming noise and duplicates.

        Why:
            Author/mention comparisons benefit from consistent formatting.

        When:
            Used after extracting a raw name from the DOM.

        How:
            Collapses whitespace, strips separators, and removes duplicate token
            sequences caused by accessibility markup.

        Args:
            name (str): Raw name string.

        Returns:
            str: Cleaned name suitable for comparisons.
        """
        if not name:
            return ""
        cleaned = " ".join(name.split())
        for sep in ("•", "|", "·"):
            cleaned = cleaned.replace(sep, " ")
        cleaned = " ".join(cleaned.split())
        tokens = cleaned.split()
        n = len(tokens)
        if n >= 2 and n % 2 == 0 and tokens[: n // 2] == tokens[n // 2 :]:
            return " ".join(tokens[: n // 2])
        for window in range(min(4, n // 2), 0, -1):
            if n >= 2 * window and tokens[:window] == tokens[window: 2 * window] and (n == 2 * window or not tokens[2 * window :]):
                return " ".join(tokens[:window])
        return cleaned

    def _find_visible_posts(self, limit: int = 8):
        """Return a list of currently visible post containers in the viewport.

        Why:
            The engage loop iterates over visible posts to decide actions.

        When:
            Called on each iteration before processing posts.

        How:
            Scans multiple selector patterns for displayed elements up to the
            provided limit.

        Args:
            limit (int): Maximum number of posts to collect.

        Returns:
            list[WebElement]: Visible post elements.
        """
        posts = []
        selectors = EngageSelectors.VISIBLE_POSTS
        for xp in selectors:
            try:
                found = self.driver.find_elements(By.XPATH, xp)
                for el in found:
                    try:
                        if el.is_displayed():
                            posts.append(el)
                            if len(posts) >= limit:
                                return posts
                    except Exception:
                        continue
            except Exception:
                continue
        return posts

    def _visible_post_keys(self, limit: int = 16):
        """Generate dedupe keys for the visible posts in the viewport.

        Why:
            Prevents duplicate interactions within a scroll cycle.

        When:
            Executed after collecting visible posts.

        How:
            Calls :meth:`_find_visible_posts` and computes keys using URNs or
            fallback hashing.

        Args:
            limit (int): Maximum number of posts to process.

        Returns:
            list[str]: Dedupe keys for each visible post.
        """
        keys = []
        posts = self._find_visible_posts(limit=limit)
        try:
            logging.info(f"SCROLL visible_posts={len(posts)}")
        except Exception:
            pass
        for root in posts:
            try:
                urn = self._extract_post_urn(root)
                key = self._post_dedupe_key(root, urn)
                keys.append(key)
            except Exception:
                continue
        return keys

    def _scroll_feed(self, wait_min: float = 1.5, wait_max: float = 3.0, *args, **kwargs):
        """Scroll the feed downward while handling stalled viewports.

        Why:
            Load new posts for the engage loop when the current viewport is exhausted.

        When:
            Called by the executor whenever progress is lacking.

        How:
            Executes scroll JavaScript, waits within configured bounds, and
            triggers fallback scrolls if height doesn't change.

        Args:
            wait_min (float): Minimum wait after scrolling.
            wait_max (float): Maximum wait after scrolling.
            *args: Ignored, allows compatibility with call sites.
            **kwargs: Ignored, allows compatibility with call sites.

        Returns:
            None
        """
        try:
            prev_h = self.driver.execute_script("return document.body.scrollHeight || document.documentElement.scrollHeight || 0;")
        except Exception:
            prev_h = None
        try:
            self.driver.execute_script("window.scrollBy(0, Math.round(window.innerHeight*0.9));")
            logging.info("SCROLL action=page_down amount=0.9vh")
        except Exception:
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                logging.info("SCROLL action=scroll_to_bottom (fallback)")
            except Exception:
                pass
        time.sleep(random.uniform(max(0.2, wait_min), max(wait_min + 0.1, wait_max)))
        try:
            new_h = self.driver.execute_script("return document.body.scrollHeight || document.documentElement.scrollHeight || 0;")
            if prev_h is not None and new_h is not None:
                delta = int(new_h) - int(prev_h)
                logging.info(f"SCROLL height_before={prev_h} height_after={new_h} delta={delta}")
                if delta <= 0:
                    try:
                        self.driver.switch_to.active_element.send_keys(Keys.END)
                        logging.info("SCROLL_FALLBACK end_key_sent")
                    except Exception:
                        try:
                            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            logging.info("SCROLL_FALLBACK js_scroll_to_bottom")
                        except Exception:
                            pass
                    ext_wait = max(float(wait_max), float(wait_min)) + random.uniform(0.8, 1.6)
                    logging.info(f"SCROLL_STALL extended_wait={ext_wait:.2f}s")
                    time.sleep(ext_wait)
                    try:
                        newer_h = self.driver.execute_script("return document.body.scrollHeight || document.documentElement.scrollHeight || 0;")
                        logging.info(f"SCROLL_STALL height_after_extended={newer_h} delta2={int(newer_h)-int(new_h)}")
                    except Exception:
                        pass
        except Exception:
            pass

    def _aggressive_load_more(self, prev_keys: List[str], tries: int = 4, wait_min: float = 1.5, wait_max: float = 3.0) -> bool:
        """Force-scroll the feed to load additional posts when stuck.

        Why:
            LinkedIn sometimes fails to load more posts on standard scroll; this
            routine nudges the viewport more aggressively.

        When:
            Called after detecting no new keys between scroll attempts.

        How:
            Scrolls to bottom, waits, scrolls up/down slightly, dismisses
            overlays, and compares keys to detect fresh content.

        Args:
            prev_keys (list[str]): Keys from the previous viewport pass.
            tries (int): Maximum aggressive attempts.
            wait_min (float): Minimum wait per attempt.
            wait_max (float): Maximum wait per attempt.

        Returns:
            bool: ``True`` if new posts surface, ``False`` otherwise.
        """
        for i in range(max(1, tries)):
            try:
                logging.info(f"SCROLL_AGG attempt={i+1}/{tries} strategy=bottom")
            except Exception:
                pass
            did_bottom = False
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                did_bottom = True
            except Exception:
                pass
            if not did_bottom:
                try:
                    self.driver.switch_to.active_element.send_keys(Keys.END)
                    logging.info("SCROLL_AGG end_key_sent")
                except Exception:
                    pass
            time.sleep(random.uniform(wait_min, wait_max))
            try:
                self.driver.execute_script("window.scrollBy(0, -Math.round(window.innerHeight*0.2));")
                time.sleep(random.uniform(0.6, 1.2))
                self.driver.execute_script("window.scrollBy(0, Math.round(window.innerHeight*0.8));")
            except Exception:
                pass
            try:
                self.dismiss_overlays()
            except Exception:
                pass
            now_keys = self._visible_post_keys(limit=20)
            if any(k not in prev_keys for k in now_keys):
                try:
                    logging.info(f"SCROLL_AGG new_posts_detected count={len([k for k in now_keys if k not in prev_keys])}")
                except Exception:
                    pass
                return True
        try:
            logging.info("SCROLL_AGG no_new_posts_after_tries")
        except Exception:
            pass
        return False

    def _find_post_root_for_bar(self, bar):
        """Locate the post container corresponding to a given action bar.

        Why:
            Many operations (author extraction, marking) require the post root.

        When:
            Invoked during comment/like flows after discovering the action bar.

        How:
            Traverses up the DOM via XPath to find a containing article/div.

        Args:
            bar (WebElement): Action bar element.

        Returns:
            WebElement: Post root element or the action bar itself if fallback.
        """
        ancestor_paths = EngageSelectors.POST_ROOT_FROM_BAR
        for xp in ancestor_paths:
            try:
                root = bar.find_element(By.XPATH, xp)
                if root:
                    return root
            except Exception:
                continue
        return bar

    def _extract_post_urn(self, root):
        """Extract the URN identifier associated with a feed post.

        Why:
            URNs uniquely identify posts and are used for deduplication and logging.

        When:
            Called while processing each post to generate dedupe keys and track history.

        How:
            Searches attributes on the root and ancestors, falling back to link
            parsing if necessary.

        Args:
            root (WebElement): Post container element.

        Returns:
            str | None: URN string or ``None`` when unavailable.
        """
        try:
            try:
                anc = root.find_element(By.XPATH, "ancestor-or-self::*[@data-urn or @data-entity-urn][1]")
                for a in ("data-urn", "data-entity-urn"):
                    val = anc.get_attribute(a)
                    if val:
                        return val
            except Exception:
                pass
            for a in ("data-urn", "data-entity-urn", "data-id"):
                try:
                    v = root.get_attribute(a)
                    if v:
                        return v
                except Exception:
                    continue
            cand = root.find_elements(By.XPATH, ".//*[@data-urn or @data-entity-urn or @data-id]")
            for el in cand:
                for a in ("data-urn", "data-entity-urn", "data-id"):
                    try:
                        v = el.get_attribute(a)
                        if v:
                            return v
                    except Exception:
                        continue
            try:
                anchors = root.find_elements(By.XPATH, ".//a[contains(@href,'/feed/update/') or contains(@href,'activity:')]")
                for a in anchors:
                    try:
                        href = a.get_attribute('href') or ''
                        m = re.search(r"urn:li:activity:\d+", href)
                        if m:
                            return m.group(0)
                    except Exception:
                        continue
            except Exception:
                pass
        except Exception:
            pass
        return None

    def _extract_data_id(self, root) -> str:
        """Retrieve a stable `data-id` attribute for dedupe purposes.

        Why:
            Some feeds expose data IDs even when URNs are missing; they help avoid duplicates.

        When:
            Called alongside URN extraction for each post.

        How:
            Checks the root and ancestor nodes for `data-id` attributes.

        Args:
            root (WebElement): Post container element.

        Returns:
            str: Data ID string or empty string when not found.
        """
        try:
            try:
                v = root.get_attribute('data-id')
                if v:
                    return v
            except Exception:
                pass
            try:
                anc = root.find_element(By.XPATH, "ancestor-or-self::*[@data-id][1]")
                v = anc.get_attribute('data-id')
                if v:
                    return v
            except Exception:
                pass
        except Exception:
            pass
        return ""

    def _post_text_key(self, root) -> str:
        """Generate a hash representing the post's author/text combination.

        Why:
            Helps identify duplicates when URNs or IDs are missing but content
            repeats within a session.

        When:
            Computed for each post processed by the engage loop.

        How:
            Gathers the author name and first text snippet, concatenates them,
            and returns a SHA-1 hash.

        Args:
            root (WebElement): Post container element.

        Returns:
            str: Hex digest representing the post content signature.
        """
        try:
            actor = ""
            try:
                actor = self._extract_author_name(root) or ""
            except Exception:
                pass
            text = ""
            try:
                snippet_nodes = root.find_elements(By.XPATH, EngageSelectors.TEXT_SNIPPETS)
                for n in snippet_nodes:
                    t = (n.text or "").strip()
                    if t:
                        text = t
                        break
            except Exception:
                pass
            src = (actor + "|" + text[:160]).strip()
            return hashlib.sha1(src.encode('utf-8', errors='ignore')).hexdigest() if src else ""
        except Exception:
            return ""

    def _post_has_user_comment(self, root) -> bool:
        """Detect whether the current user already commented on the post.

        Why:
            Prevents duplicate comments that could flag automation behaviour.

        When:
            Checked before composing a new comment on a post.

        How:
            Searches for rendered comment items containing "You" or similar markers.

        Args:
            root (WebElement): Post container element.

        Returns:
            bool: ``True`` if a user-authored comment exists, else ``False``.
        """
        try:
            paths = EngageSelectors.USER_COMMENT_MARKERS
            for xp in paths:
                try:
                    nodes = root.find_elements(By.XPATH, xp)
                    for n in nodes:
                        try:
                            if n.is_displayed():
                                return True
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _post_has_similar_comment(self, root, text: Optional[str]) -> bool:
        """Check whether a comment similar to the candidate text already exists.

        Why:
            Avoids posting duplicate comments with comparable semantics.

        When:
            Evaluated before submitting a new comment.

        How:
            Normalises and truncates the candidate text, then scans existing
            comments for the signature.

        Args:
            root (WebElement): Post container element.
            text (str | None): Candidate comment text.

        Returns:
            bool: ``True`` if a similar comment is found, otherwise ``False``.
        """
        try:
            if not text:
                return False
            sig = re.sub(r"\s+", " ", str(text)).strip()
            sig = re.sub(r"[^\w\s.,!?@#:+-]", "", sig)
            if len(sig) < 8:
                return False
            sig = sig[:32].lower()
            paths = EngageSelectors.ALL_COMMENTS
            for xp in paths:
                try:
                    nodes = root.find_elements(By.XPATH, xp)
                    for n in nodes:
                        try:
                            if not n.is_displayed():
                                continue
                            txt = (n.text or "").strip().lower()
                            if sig and sig in txt:
                                return True
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _extract_text_for_ai(self, root, post_extractor=None) -> str:
        """Harvest readable text from a post for AI summarisation.

        Why:
            AI comment generation needs clean text to summarise and respond.

        When:
            Called prior to invoking the OpenAI client for a post.

        How:
            Uses :class:`PostExtractor` when available, falling back to DOM
            queries and raw text extraction with truncation.

        Args:
            root (WebElement): Post container.
            post_extractor: Optional :class:`PostExtractor` instance.

        Returns:
            str: Extracted text truncated to ~1200 characters.
        """
        if post_extractor and hasattr(post_extractor, "extract_text"):
            try:
                text = post_extractor.extract_text(root)
                if text:
                    return text.strip()
            except Exception:
                pass
        try:
            selectors = EngageSelectors.AI_TEXT_NODES
            parts: List[str] = []
            seen = set()
            for xp in selectors:
                nodes = root.find_elements(By.XPATH, xp)
                for node in nodes:
                    try:
                        if not node.is_displayed():
                            continue
                        txt = (node.text or "").strip()
                        if not txt or txt in seen:
                            continue
                        parts.append(txt)
                        seen.add(txt)
                    except Exception:
                        continue
                if parts:
                    break
            if not parts:
                raw = (root.text or "").strip()
                return raw[:1200]
            combined = "\n".join(parts).strip()
            return combined[:1200]
        except Exception:
            try:
                raw = (root.text or "").strip()
                return raw[:1200]
            except Exception:
                return ""

    def _load_engage_state(self) -> Dict:
        """Load persisted engage-state metadata from disk.

        Why:
            Track previously commented URNs across runs to avoid duplicates.

        When:
            Called before an engage session begins.

        How:
            Reads ``logs/engage_state.json`` if present and returns its contents.

        Returns:
            dict: Parsed engage state or an empty dictionary when unavailable.
        """
        try:
            p = Path(config.LOG_DIRECTORY)
            p.mkdir(exist_ok=True)
            fpath = p / 'engage_state.json'
            if fpath.exists():
                with open(fpath, 'r', encoding='utf-8') as f:
                    return json.load(f) or {}
        except Exception:
            pass
        return {}

    def _save_engage_state(self, state: Dict) -> None:
        """Persist current engage-state metadata to disk.

        Why:
            Maintain history across runs for deduplication and throttling.

        When:
            Called after updating comment history during an engage session.

        How:
            Writes the provided dictionary to ``logs/engage_state.json`` using
            UTF-8 encoding and indenting for readability.

        Args:
            state (dict): State payload to persist.

        Returns:
            None
        """
        try:
            p = Path(config.LOG_DIRECTORY)
            p.mkdir(exist_ok=True)
            fpath = p / 'engage_state.json'
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _post_dedupe_key(self, root, urn: Optional[str]) -> str:
        """Produce a dedupe key for a post using text content or URN.

        Why:
            Engage logic needs to avoid engaging with the same content twice,
            even if it's a repost (which generates a new URN).

        When:
            Called for each post before processing actions.

        How:
            Prioritizes a hash of the post's text. Falls back to URN if text is empty.

        Args:
            root (WebElement): Post container element.
            urn (str | None): Extracted URN if available.

        Returns:
            str: Deterministic dedupe key.
        """
        text = ""
        try:
            snippet_nodes = root.find_elements(By.XPATH, EngageSelectors.TEXT_SNIPPETS)
            if snippet_nodes:
                # Extract up to 300 characters of text to form a solid fingerprint
                text = " ".join([n.text.strip() for n in snippet_nodes if n.text.strip()])[:300]
        except Exception:
            pass
            
        import hashlib
        if text:
            # Hash just the text to catch reposts of the same content
            return "text_" + hashlib.md5(text.encode('utf-8')).hexdigest()
        
        if urn:
            return urn
            
        # Absolute fallback if both text and URN fail
        actor = ""
        try:
            actor = self._extract_author_name(root) or ""
        except Exception:
            pass
            
        raw = f"{actor}::{id(root)}"
        return "hash_" + hashlib.md5(raw.encode('utf-8')).hexdigest()

    def _is_promoted_post(self, root) -> bool:
        """Determine whether a post is marked as promoted/sponsored.

        Why:
            Engagement defaults to skipping promoted posts unless explicitly allowed.

        When:
            Evaluated for each post before deciding to interact.

        How:
            Searches for visible nodes containing the word "promoted" in the post tree.

        Args:
            root (WebElement): Post container element.

        Returns:
            bool: ``True`` if the post appears to be promoted, else ``False``.
        """
        try:
            xp = EngageSelectors.PROMOTED_MARKER
            els = root.find_elements(By.XPATH, xp)
            for el in els:
                try:
                    if el.is_displayed():
                        txt = (el.text or "").strip().lower()
                        if "promoted" in txt:
                            return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _like_from_bar(self, bar) -> bool:
        """Like a post using controls within its action bar.

        Why:
            Provides a reusable helper for both engage and courtesy-like flows.

        When:
            Called after locating the post's action bar.

        How:
            Searches for like buttons, ensures they are not already pressed,
            scrolls into view if needed, and clicks using fallbacks.

        Args:
            bar (WebElement): Action bar element containing social buttons.

        Returns:
            bool: ``True`` if the like action succeeds, else ``False``.
        """
        try:
            btn = None
            for sel in EngageSelectors.LIKE_BUTTONS:
                try:
                    el = WebDriverWait(bar, 3).until(EC.presence_of_element_located((By.XPATH, sel)))
                    if el and el.is_displayed():
                        btn = el
                        break
                except Exception:
                    continue
            if not btn:
                return False
            pressed = (btn.get_attribute("aria-pressed") or "").lower() == "true"
            if pressed:
                return False
            try:
                self._scroll_into_view(btn)
            except Exception:
                pass
            return self._click_element_with_fallback(btn, "Like (stream)")
        except Exception:
            return False

    def _comment_from_bar(self, bar, text: str, mention_author: bool = False, mention_position: str = 'append', author_name: Optional[str] = None) -> bool:
        """Submit a comment using a post's action bar and comment editor.

        Why:
            Core helper for engage-stream commenting and CLI one-shots.

        When:
            Called after determining a comment should be left on a specific post.

        How:
            Opens the comment editor, prepares text (including optional author
            mentions and inline placeholders), types or injects the comment, and
            clicks the post button with fallbacks.

        Args:
            bar (WebElement): Post action bar element.
            text (str): Comment content to submit.
            mention_author (bool): Whether to force an author mention.
            mention_position (str): Placement for author mention tokens.
            author_name (str | None): Optional pre-extracted author name.

        Returns:
            bool: ``True`` on apparent success, ``False`` otherwise.
        """
        if not text:
            return False
        try:
            opened = False
            for sel in EngageSelectors.COMMENT_BUTTONS:
                try:
                    btn = bar.find_element(By.XPATH, sel)
                    if btn and btn.is_displayed():
                        if self._click_element_with_fallback(btn, "Comment (stream)"):
                            opened = True
                            break
                except Exception:
                    continue
            if not opened:
                return False

            editor = None
            root = None
            try:
                root = self._find_post_root_for_bar(bar)
            except Exception:
                root = None
            search_context = root if root is not None else bar
            candidates = EngageSelectors.COMMENT_EDITOR
            for xp in candidates:
                try:
                    editor = WebDriverWait(search_context, 4).until(
                        EC.presence_of_element_located((By.XPATH, xp))
                    )
                    if editor and editor.is_displayed():
                        break
                except Exception:
                    continue
            if not editor:
                return False

            try:
                self._click_element_with_fallback(editor, "comment editor (stream)")
            except Exception:
                pass

            base_text = text or ""
            author = None
            if mention_author:
                author = author_name
                if author is None:
                    try:
                        if root is None:
                            root = self._find_post_root_for_bar(bar)
                    except Exception:
                        root = None
                    try:
                        author = self._extract_author_name(root) if root is not None else None
                    except Exception:
                        author = None

            if mention_author and author and (mention_position or 'append') == 'prepend':
                try:
                    logging.info("COMMENT_ORDER mention=prepend")
                except Exception:
                    pass
                try:
                    self._insert_mentions(editor, [author], leading_space=False, force_start=True)
                    try:
                        editor.send_keys(" ")
                    except Exception:
                        pass
                except Exception as e:
                    logging.warning(f"Error during prepend mention insertion: {e}")

            if hasattr(self, "_post_text_contains_inline_mentions") and \
               self._post_text_contains_inline_mentions(base_text):
                logging.info(f"Composing text with inline mentions: {base_text[:50]}...")
                if not self._compose_text_with_mentions(editor, base_text):
                    return False
            else:
                # Sanitize text for ChromeDriver (remove non-BMP characters like emojis)
                # to prevent "ChromeDriver only supports characters in the BMP" error.
                safe_text = base_text
                try:
                    if hasattr(self, "_sanitize_bmp"):
                        safe_text = self._sanitize_bmp(base_text)
                except Exception:
                    pass

                try:
                    # Re-focus editor to ensure keys reach it after mention logic
                    try:
                        self.driver.execute_script("arguments[0].focus();", editor)
                        self.random_delay(0.1, 0.3)
                    except Exception:
                        pass
                    
                    logging.info(f"Typing base comment text: {safe_text[:50]}...")
                    editor.send_keys(safe_text)
                except Exception as e:
                    logging.warning(f"Standard send_keys failed for comment text: {e}")
                    try:
                        # Use JS to APPEND the original text (including emojis)
                        # instead of overwriting the entire innerHTML (which removes mentions).
                        cleaned = base_text.replace('\n', '<br>')
                        self.driver.execute_script("""
                            const editor = arguments[0];
                            const html = arguments[1];
                            editor.focus();
                            // Attempt to insert at the end of the content
                            editor.insertAdjacentHTML('beforeend', html);
                            // Trigger input event so LinkedIn's editor detects the change
                            editor.dispatchEvent(new Event('input', { bubbles: true }));
                        """, editor, cleaned)
                        logging.info("Appended comment text via JavaScript fallback.")
                    except Exception as js_e:
                        logging.error(f"Failed to append comment text via JS: {js_e}")
                        return False

            if mention_author and author and (mention_position or 'append') == 'append':
                try:
                    logging.info("COMMENT_ORDER mention=append")
                except Exception:
                    pass
                try:
                    try:
                        self._move_caret_to_end(editor)
                    except Exception:
                        pass
                    try:
                        editor.send_keys(" ")
                    except Exception:
                        pass
                    self._insert_mentions(editor, [author], leading_space=True, force_end=True)
                    try:
                        editor.send_keys(" ")
                    except Exception:
                        pass
                except Exception:
                    try:
                        editor.send_keys(f" @{author} ")
                    except Exception:
                        pass
                try:
                    verified = self._verify_mention_entity(editor, author, timeout=2)
                except Exception:
                    verified = False
                if not verified:
                    logging.warning(f"Mention for {author} was not verified as an entity, but leaving it as typed text to prevent duplicates.")

            for sel in EngageSelectors.SUBMIT_COMMENT:
                try:
                    try:
                        logging.info("DISMISS before_submit: global search/typeahead overlay")
                        self._dismiss_global_search_overlay()
                    except Exception:
                        pass
                    post_btn = WebDriverWait(self.driver, 4).until(
                        EC.element_to_be_clickable((By.XPATH, sel))
                    )
                    try:
                        self._scroll_into_view(post_btn)
                    except Exception:
                        pass
                    if self._click_element_with_fallback(post_btn, "Submit comment (stream)"):
                        try:
                            root = self._find_post_root_for_bar(bar)
                            if root is None:
                                root = bar
                            self.driver.execute_script(
                                "arguments[0].setAttribute('data-li-bot-commented','1');", root
                            )
                        except Exception:
                            pass
                        try:
                            editor = root.find_element(By.XPATH, ".//div[@contenteditable='true']")
                            try:
                                editor.send_keys(Keys.ESCAPE)
                            except Exception:
                                pass
                            try:
                                self.driver.execute_script("arguments[0].blur && arguments[0].blur();", editor)
                            except Exception:
                                pass
                        except Exception:
                            pass
                        return True
                except Exception:
                    continue
        except Exception:
            return False
        return False

    def _repost_from_bar(self, bar, thoughts_text: str, mention_author: bool = False, mention_position: str = 'append', author_name: Optional[str] = None) -> bool:
        """Submit a repost using a post's action bar.
        
        Args:
            bar: Action bar element.
            thoughts_text: Commentary to accompany the repost.
            mention_author: Whether to force an author mention.
            mention_position: Placement for author mention tokens.
            author_name: Optional pre-extracted author name.
            
        Returns:
            bool: True on success, False otherwise.
        """
        if not thoughts_text:
            return False
            
        try:
            from ui_selectors import FeedActionSelectors
            repost_btn = None
            for sel in FeedActionSelectors.REPOST_BUTTONS:
                try:
                    btn = bar.find_element(By.XPATH, sel)
                    if btn and btn.is_displayed():
                        repost_btn = btn
                        break
                except Exception:
                    continue
            if not repost_btn:
                return False
            if not self._click_element_with_fallback(repost_btn, "Repost dropdown"):
                return False
            self.random_delay(0.4, 0.8)

            dropdown_containers = []
            for xp in FeedActionSelectors.REPOST_DROPDOWN_CONTAINERS_SCOPED:
                try:
                    c = WebDriverWait(bar, 2).until(EC.presence_of_element_located((By.XPATH, xp)))
                    if c and c.is_displayed():
                        dropdown_containers.append(c)
                except Exception:
                    continue
            if not dropdown_containers:
                try:
                    c = WebDriverWait(self.driver, 2).until(
                        EC.presence_of_element_located((By.XPATH, FeedActionSelectors.REPOST_DROPDOWN_CONTAINERS_GLOBAL))
                    )
                    if c:
                        dropdown_containers.append(c)
                except Exception:
                    pass

            text_candidates = FeedActionSelectors.REPOST_CANDIDATE_TEXTS
            
            option = None
            for container in dropdown_containers:
                tag_sets = FeedActionSelectors.REPOST_OPTION_TAGS
                for ts in tag_sets:
                    try:
                        nodes = container.find_elements(By.XPATH, ts)
                    except Exception:
                        nodes = []
                    for n in nodes:
                        try:
                            if not n.is_displayed(): continue
                            txt = (n.text or "").strip().lower()
                            if not txt: continue
                            for cand in text_candidates:
                                if cand in txt:
                                    option = n
                                    break
                            if option: break
                        except Exception:
                            continue
                    if option: break
                if option: break
            
            if not option:
                return False
            if not self._click_element_with_fallback(option, "Repost with your thoughts"):
                return False
            self.random_delay(0.6, 1.2)

            editor = None
            for xp in FeedActionSelectors.REPOST_EDITOR:
                try:
                    editor = WebDriverWait(self.driver, 6).until(
                        EC.presence_of_element_located((By.XPATH, xp))
                    )
                    if editor and editor.is_displayed():
                        break
                except Exception:
                    continue
            if not editor:
                return False
            try:
                self._click_element_with_fallback(editor, "repost editor focus")
            except Exception:
                pass

            # Sanitize for ChromeDriver BMP limitation
            safe_thoughts = thoughts_text
            try:
                if hasattr(self, "_sanitize_bmp"):
                    safe_thoughts = self._sanitize_bmp(thoughts_text)
            except Exception:
                pass

            try:
                editor.send_keys(safe_thoughts)
            except Exception:
                try:
                    cleaned = thoughts_text.replace('\n', '<br>')
                    self.driver.execute_script("""
                        const editor = arguments[0];
                        const html = arguments[1];
                        editor.focus();
                        editor.insertAdjacentHTML('beforeend', html);
                        editor.dispatchEvent(new Event('input', { bubbles: true }));
                    """, editor, cleaned)
                except Exception:
                    return False

            if mention_author:
                author = author_name
                if not author:
                    try:
                        root = self._find_post_root_for_bar(bar)
                        author = self._extract_author_name(root) if root else None
                    except Exception:
                        pass
                if author:
                    if (mention_position or 'append') == 'prepend':
                        try: self._move_caret_to_start(editor)
                        except Exception: pass
                        self._insert_mentions(editor, [author], leading_space=False, force_start=True)
                        try: editor.send_keys(" ")
                        except Exception: pass
                    else:
                        try: self._move_caret_to_end(editor)
                        except Exception: pass
                        try: editor.send_keys(" ")
                        except Exception: pass
                        self._insert_mentions(editor, [author], leading_space=True, force_end=True)
                        try: editor.send_keys(" ")
                        except Exception: pass
            
            for sel in FeedActionSelectors.SUBMIT_REPOST:
                try:
                    post_btn = WebDriverWait(self.driver, 4).until(
                        EC.element_to_be_clickable((By.XPATH, sel))
                    )
                    if self._click_element_with_fallback(post_btn, "Submit repost"):
                        return True
                except Exception:
                    continue
            return False
            
        except Exception:
            return False

    def _scroll_into_view(self, el):
        """Scroll the viewport so the provided element becomes visible.

        Why:
            Some interactions fail when elements are offscreen; scrolling first
            improves reliability.

        When:
            Called before clicking buttons in the engage flow.

        How:
            Executes a simple JavaScript ``scrollIntoView`` call.

        Args:
            el (WebElement): Element to bring into view.

        Returns:
            None
        """
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except Exception:
            pass
