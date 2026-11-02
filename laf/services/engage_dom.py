"""DOM traversal and interaction service supporting the engage stream.

WHY
  Keep low-level page reads and actions in one place, so the engage flow can
  focus on decisions instead of selectors and fallbacks.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from laf.selectors.engage import EngageSelectors
from laf.selectors.feed import FeedActionSelectors

from ..ui import UiActions
from .engage_utils import reaction_already_set
from .mentions import MentionService
from .overlays import OverlayService

logger = logging.getLogger(__name__)

class EngageDomService:
    """Provide DOM traversal, extraction and interaction helpers.

    WHY
      Read and act on feed posts behind one service, so the flow code does not
      depend on the current LinkedIn page shape.
    """

    def __init__(
        self, ui: UiActions, overlays: OverlayService, mentions: MentionService
    ) -> None:
        """
        WHY
          Give the engage DOM helpers the shared driver, overlay cleanup and
          mention tools so scrolling, reading and acting on a post all work.

        Args
          ui: UiActions, the shared Selenium action helper.
          overlays: OverlayService, used to dismiss dialogs over the feed.
          mentions: MentionService, used when comments carry author mentions.

        MUTATIONS
          Stores the partners and reads the config from the UI helper.
        """
        self.ui = ui
        self.overlays = overlays
        self.mentions = mentions
        self.config = ui.config

    # ------------------------------------------------------------------
    # Author extraction utilities

    def extract_author_name(self, root) -> Optional[str]:
        """Extract the post author display name on a best-effort basis.

        WHY
          Feed mention placement, dedupe keys and logs need the author name,
          and the page markup varies, so try each known selector and the
          aria-label before giving up.

        Args
          root: WebElement, the post container from the caller.

        Returns
          Optional[str], the normalised author name, or None when no readable
          name is found.
        """
        if root is None:
            return None

        from_label = self._author_name_from_profile_label(root)
        if from_label:
            return from_label

        selectors = EngageSelectors.AUTHOR_NAME

        for xp in selectors:
            try:
                for node in root.find_elements(By.XPATH, xp):
                    if not node.is_displayed():
                        continue
                    candidate = self._normalize_person_name(node.text)
                    if candidate:
                        return candidate
            except WebDriverException:
                continue

        # Fallback: parse aria-label fragments like "Post by Jane Doe"
        try:
            aria = (root.get_attribute("aria-label") or "").strip()
            if aria:
                for marker in ("by ", "for "):
                    if marker in aria:
                        fragment = aria.split(marker, 1)[1].strip()
                        fragment = re.split(
                            "[|•·\\-–\\u2014]|\\s{2,}", fragment
                        )[0].strip()
                        candidate = self._normalize_person_name(fragment)
                        if candidate:
                            return candidate
        except WebDriverException:
            pass

        return None

    def _author_name_from_profile_label(self, root) -> Optional[str]:
        """Read the author name from the avatar's accessibility label.

        WHY
          The new feed prints the author name twice, once in a hidden label that
          adds "Verified Profile" and degree words. The avatar label names the
          person alone, so it gives a clean name without those extra words.

        Args
          root: WebElement, the post container from the caller.

        Returns
          Optional[str], the normalised author name, or None when no avatar
          label is found or it does not hold a name.
        """
        path = (
            ".//*[@alt and starts-with(@alt,'View ')]"
            " | .//*[@aria-label and starts-with(@aria-label,'View ')]"
        )
        try:
            nodes = root.find_elements(By.XPATH, path)
        except WebDriverException:
            return None
        for node in nodes:
            label = node.get_attribute("alt") or node.get_attribute("aria-label") or ""
            match = re.match(r"^\s*View\s+(.+?)[’']s profile\s*$", label)
            if not match:
                continue
            candidate = self._normalize_person_name(match.group(1))
            if candidate:
                return candidate
        return None

    def _normalize_person_name(self, name: str) -> str:
        """Clean a raw name string so comparisons and mentions match.

        WHY
          Accessibility markup repeats and pads names, so trim whitespace,
          drop separators and remove the repeated token blocks before use.

        Args
          name: str, the raw name read from the DOM.

        Returns
          str, the cleaned name, or an empty string when the input is empty.
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
            if (
                n >= 2 * window
                and tokens[:window] == tokens[window : 2 * window]
                and (n == 2 * window or not tokens[2 * window :])
            ):
                return " ".join(tokens[:window])
        return cleaned

    def find_visible_posts(self, limit: int = 8):
        """Return the post containers that are visible in the viewport.

        WHY
          The engage loop can only act on posts it can see, so collect the
          displayed ones across the known selector patterns.

        Args
          limit: int, the maximum number of posts to collect.

        Returns
          List[WebElement], the visible post elements, possibly fewer than the
          limit.
        """
        posts = []
        selectors = EngageSelectors.VISIBLE_POSTS
        for xp in selectors:
            try:
                found = self.ui.driver.find_elements(By.XPATH, xp)
                for el in found:
                    try:
                        if el.is_displayed():
                            posts.append(el)
                            if len(posts) >= limit:
                                return posts
                    except WebDriverException:
                        continue
            except WebDriverException:
                continue
        return posts

    def visible_post_keys(self, limit: int = 16):
        """Generate dedupe keys for the visible posts in the viewport.

        WHY
          Let the caller compare two scroll passes and tell whether new posts
          arrived, without reading each post again.

        Args
          limit: int, the maximum number of posts to read.

        Returns
          List[str], one dedupe key per readable visible post.
        """
        keys = []
        posts = self.find_visible_posts(limit=limit)
        logger.info(f"SCROLL visible_posts={len(posts)}")
        for root in posts:
            try:
                urn = self.extract_post_urn(root)
                key = self.post_dedupe_key(root, urn)
                keys.append(key)
            except WebDriverException:
                continue
        return keys

    def scroll_feed(self, wait_min: float = 1.5, wait_max: float = 3.0, *args, **kwargs):
        """Scroll the feed downward while handling stalled viewports.

        WHY
          Load new posts when the current viewport is exhausted. When the page
          height does not grow, send End or scroll to the bottom and wait
          longer, so a slow load does not look like the end of the feed.

        Args
          wait_min: float, the minimum wait after scrolling.
          wait_max: float, the maximum wait after scrolling.
          *args: positional values, ignored and kept for call site compatibility.
          **kwargs: keyword values, ignored and kept for call site compatibility.

        MUTATIONS
          Scrolls the browser viewport and blocks the thread while waiting.
        """
        try:
            prev_h = self.ui.driver.execute_script(
                "return document.body.scrollHeight || document.documentElement.scrollHeight || 0;"
            )
        except WebDriverException:
            prev_h = None
        try:
            self.ui.driver.execute_script(
                "window.scrollBy(0, Math.round(window.innerHeight*0.9));"
            )
            logger.info("SCROLL action=page_down amount=0.9vh")
        except WebDriverException:
            try:
                self.ui.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                logger.info("SCROLL action=scroll_to_bottom (fallback)")
            except WebDriverException:
                pass
        time.sleep(random.uniform(max(0.2, wait_min), max(wait_min + 0.1, wait_max)))
        try:
            new_h = self.ui.driver.execute_script(
                "return document.body.scrollHeight || document.documentElement.scrollHeight || 0;"
            )
            if prev_h is not None and new_h is not None:
                delta = int(new_h) - int(prev_h)
                logger.info(f"SCROLL height_before={prev_h} height_after={new_h} delta={delta}")
                if delta <= 0:
                    try:
                        self.ui.driver.switch_to.active_element.send_keys(Keys.END)
                        logger.info("SCROLL_FALLBACK end_key_sent")
                    except WebDriverException:
                        try:
                            self.ui.driver.execute_script(
                                "window.scrollTo(0, document.body.scrollHeight);"
                            )
                            logger.info("SCROLL_FALLBACK js_scroll_to_bottom")
                        except WebDriverException:
                            pass
                    ext_wait = max(float(wait_max), float(wait_min)) + random.uniform(0.8, 1.6)
                    logger.info(f"SCROLL_STALL extended_wait={ext_wait:.2f}s")
                    time.sleep(ext_wait)
                    try:
                        newer_h = self.ui.driver.execute_script(
                            "return document.body.scrollHeight || "
                            "document.documentElement.scrollHeight || 0;"
                        )
                        logger.info(
                            f"SCROLL_STALL height_after_extended={newer_h} "
                            f"delta2={int(newer_h) - int(new_h)}"
                        )
                    except (WebDriverException, TypeError, ValueError):
                        pass
        except (WebDriverException, TypeError, ValueError):
            pass

    def aggressive_load_more(
        self, prev_keys: List[str], tries: int = 4, wait_min: float = 1.5, wait_max: float = 3.0
    ) -> bool:
        """Force-scroll the feed to load more posts when it looks stuck.

        WHY
          LinkedIn sometimes ignores a normal scroll, so push the viewport to
          the bottom and back, dismiss overlays, and check for new keys before
          the caller gives up.

        Args
          prev_keys: List[str], the keys from the previous viewport pass.
          tries: int, the maximum number of attempts.
          wait_min: float, the minimum wait per attempt.
          wait_max: float, the maximum wait per attempt.

        Returns
          bool, True when a new post key appears, False when none appeared
          after all tries.

        MUTATIONS
          Scrolls the browser viewport, dismisses overlays and blocks the
          thread between attempts.
        """
        for i in range(max(1, tries)):
            logger.info(f"SCROLL_AGG attempt={i + 1}/{tries} strategy=bottom")
            did_bottom = False
            try:
                self.ui.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                did_bottom = True
            except WebDriverException:
                pass
            if not did_bottom:
                try:
                    self.ui.driver.switch_to.active_element.send_keys(Keys.END)
                    logger.info("SCROLL_AGG end_key_sent")
                except WebDriverException:
                    pass
            time.sleep(random.uniform(wait_min, wait_max))
            try:
                self.ui.driver.execute_script(
                    "window.scrollBy(0, -Math.round(window.innerHeight*0.2));"
                )
                time.sleep(random.uniform(0.6, 1.2))
                self.ui.driver.execute_script(
                    "window.scrollBy(0, Math.round(window.innerHeight*0.8));"
                )
            except WebDriverException:
                pass
            self.overlays.dismiss_overlays()
            now_keys = self.visible_post_keys(limit=20)
            if any(k not in prev_keys for k in now_keys):
                logger.info(
                    f"SCROLL_AGG new_posts_detected "
                    f"count={len([k for k in now_keys if k not in prev_keys])}"
                )
                return True
        logger.info("SCROLL_AGG no_new_posts_after_tries")
        return False

    def find_post_root_for_bar(self, bar):
        """Locate the post container that holds a given action bar.

        WHY
          Author reads and comment marks need the post root. When no ancestor
          matches, return the bar itself so the caller still has a usable node.

        Args
          bar: WebElement, the action bar found inside the post.

        Returns
          WebElement, the ancestor post root, or the bar when no match is found.
        """
        ancestor_paths = EngageSelectors.POST_ROOT_FROM_BAR
        for xp in ancestor_paths:
            try:
                root = bar.find_element(By.XPATH, xp)
                if root:
                    return root
            except WebDriverException:
                continue
        return bar

    def extract_post_urn(self, root):
        """Extract the URN identifier associated with a feed post.

        WHY
          A URN identifies the post across runs, so its history and logs can be
          matched. Try the root, its ancestors and activity links, because the
          attribute location changes with the page markup.

        Args
          root: WebElement, the post container from the caller.

        Returns
          Optional[str], the URN string, or None when none is found.
        """
        try:
            try:
                anc = root.find_element(
                    By.XPATH, "ancestor-or-self::*[@data-urn or @data-entity-urn][1]"
                )
                for a in ("data-urn", "data-entity-urn"):
                    val = anc.get_attribute(a)
                    if val:
                        return val
            except WebDriverException:
                pass
            for a in ("data-urn", "data-entity-urn", "data-id"):
                try:
                    v = root.get_attribute(a)
                    if v:
                        return v
                except WebDriverException:
                    continue
            cand = root.find_elements(By.XPATH, ".//*[@data-urn or @data-entity-urn or @data-id]")
            for el in cand:
                for a in ("data-urn", "data-entity-urn", "data-id"):
                    try:
                        v = el.get_attribute(a)
                        if v:
                            return v
                    except WebDriverException:
                        continue
            try:
                anchors = root.find_elements(
                    By.XPATH, ".//a[contains(@href,'/feed/update/') or contains(@href,'activity:')]"
                )
                for a in anchors:
                    try:
                        href = a.get_attribute("href") or ""
                        m = re.search(r"urn:li:activity:\d+", href)
                        if m:
                            return m.group(0)
                    except WebDriverException:
                        continue
            except WebDriverException:
                pass
        except WebDriverException:
            pass
        return None

    def extract_data_id(self, root) -> str:
        """Retrieve a stable data-id attribute for dedupe.

        WHY
          Some feeds expose a data ID even when no URN exists, so the run can
          still tell one post from another.

        Args
          root: WebElement, the post container from the caller.

        Returns
          str, the data ID, or an empty string when not found.
        """
        try:
            try:
                v = root.get_attribute("data-id")
                if v:
                    return v
            except WebDriverException:
                pass
            try:
                anc = root.find_element(By.XPATH, "ancestor-or-self::*[@data-id][1]")
                v = anc.get_attribute("data-id")
                if v:
                    return v
            except WebDriverException:
                pass
        except WebDriverException:
            pass
        return ""

    def post_text_key(self, root) -> str:
        """Generate a hash of the post author and first text snippet.

        WHY
          Identify a repeated post when the URN or data ID is missing, using
          the content the run can actually see.

        Args
          root: WebElement, the post container from the caller.

        Returns
          str, a hex digest signature, or an empty string when no content was
          read.
        """
        try:
            actor = ""
            try:
                actor = self.extract_author_name(root) or ""
            except WebDriverException:
                pass
            text = ""
            try:
                snippet_nodes = root.find_elements(By.XPATH, EngageSelectors.TEXT_SNIPPETS)
                for n in snippet_nodes:
                    t = (n.text or "").strip()
                    if t:
                        text = t
                        break
            except WebDriverException:
                pass
            src = (actor + "|" + text[:160]).strip()
            return hashlib.sha1(src.encode("utf-8", errors="ignore")).hexdigest() if src else ""
        except WebDriverException:
            return ""

    def post_has_user_comment(self, root) -> bool:
        """Detect whether the current user already commented on the post.

        WHY
          A second comment of our own on the same post looks automated, so
          check the rendered comment markers before composing a new one.

        Args
          root: WebElement, the post container from the caller.

        Returns
          bool, True when a user-authored comment marker is visible, False
          otherwise.
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
                        except WebDriverException:
                            continue
                except WebDriverException:
                    continue
        except WebDriverException:
            pass
        return False

    def post_has_similar_comment(self, root, text: Optional[str]) -> bool:
        """Check whether a comment similar to the candidate text already exists.

        WHY
          Avoid posting a near duplicate of a comment already on the post,
          which would make the run look automated.

        Args
          root: WebElement, the post container from the caller.
          text: Optional[str], the comment text about to be posted.

        Returns
          bool, True when a matching signature is visible, False otherwise.
          An empty or very short candidate is always False.
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
                        except WebDriverException:
                            continue
                except WebDriverException:
                    continue
        except WebDriverException:
            pass
        return False

    def extract_text_for_ai(self, root, post_extractor=None) -> str:
        """Harvest readable text from a post for AI summarisation.

        WHY
          AI comment generation needs clean text. Prefer the supplied
          extractor, then known text selectors, then the raw node text, all
          cut to about 1200 characters so the prompt stays small.

        Args
          root: WebElement, the post container from the caller.
          post_extractor: Any, an optional extractor with an extract_text
            method.

        Returns
          str, the extracted text capped near 1200 characters, or an empty
          string when nothing readable is found.
        """
        if post_extractor and hasattr(post_extractor, "extract_text"):
            try:
                text = post_extractor.extract_text(root)
                if text:
                    return text.strip()
            except WebDriverException:
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
                    except WebDriverException:
                        continue
                if parts:
                    break
            if not parts:
                raw = (root.text or "").strip()
                return raw[:1200]
            combined = "\n".join(parts).strip()
            return combined[:1200]
        except WebDriverException:
            try:
                raw = (root.text or "").strip()
                return raw[:1200]
            except WebDriverException:
                return ""

    def load_engage_state(self) -> Dict:
        """Load persisted engage-state metadata from disk.

        WHY
          Comment history must survive between runs, so previously handled
          URNs are not commented again. A missing or unreadable file yields an
          empty state instead of an error.

        Returns
          Dict, the parsed state, or an empty dict when the file is absent or
          cannot be read.

        MUTATIONS
          Creates the log directory when it is missing.
        """
        try:
            p = Path(self.config.log_directory)
            p.mkdir(exist_ok=True)
            fpath = p / "engage_state.json"
            if fpath.exists():
                with open(fpath, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
        except (OSError, ValueError):
            pass
        return {}

    def save_engage_state(self, state: Dict) -> None:
        """Persist the current engage-state metadata to disk.

        WHY
          Keep comment history across runs so the next run can skip posts
          already handled. A write failure is swallowed so it cannot stop the
          session.

        Args
          state: Dict, the state payload from the caller.

        MUTATIONS
          Creates the log directory when missing and overwrites
          ``logs/engage_state.json`` with the JSON state.
        """
        try:
            p = Path(self.config.log_directory)
            p.mkdir(exist_ok=True)
            fpath = p / "engage_state.json"
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except (OSError, TypeError):
            pass

    def post_dedupe_key(self, root, urn: Optional[str]) -> str:
        """Produce a dedupe key for a post using its text or its URN.

        WHY
          A repost gets a new URN but keeps the same text, so the text hash is
          tried first to catch it. The URN and a fallback hash cover posts
          with no readable text.

        Args
          root: WebElement, the post container from the caller.
          urn: Optional[str], the URN found for the post.

        Returns
          str, a deterministic key: text hash, then URN, then a local hash.
        """
        text = ""
        try:
            snippet_nodes = root.find_elements(By.XPATH, EngageSelectors.TEXT_SNIPPETS)
            if snippet_nodes:
                # Extract up to 300 characters of text to form a solid fingerprint
                text = " ".join([n.text.strip() for n in snippet_nodes if n.text.strip()])[:300]
        except WebDriverException:
            pass

        if text:
            # Hash just the text to catch reposts of the same content
            return "text_" + hashlib.md5(text.encode("utf-8")).hexdigest()

        if urn:
            return urn

        # Absolute fallback if both text and URN fail
        actor = ""
        try:
            actor = self.extract_author_name(root) or ""
        except WebDriverException:
            pass

        raw = f"{actor}::{id(root)}"
        return "hash_" + hashlib.md5(raw.encode("utf-8")).hexdigest()

    def is_promoted_post(self, root) -> bool:
        """Determine whether a post is marked as promoted or sponsored.

        WHY
          The run skips promoted posts by default, so the flow needs a check
          on the visible marker text before it acts.

        Args
          root: WebElement, the post container from the caller.

        Returns
          bool, True when a visible marker contains "promoted", False otherwise.
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
                except WebDriverException:
                    continue
        except WebDriverException:
            pass
        return False

    def like_from_bar(self, bar) -> bool:
        """Like a post using controls within its action bar.

        WHY
          Give the engage and courtesy-like paths one click helper that does
          nothing when the button is missing or already pressed.

        Args
          bar: WebElement, the action bar that holds the social buttons.

        Returns
          bool, True when the click was attempted and reported success, False
          when no button was found, it was already pressed, or the click failed.
        """
        try:
            btn = None
            for sel in EngageSelectors.LIKE_BUTTONS:
                try:
                    el = WebDriverWait(bar, 3).until(
                        EC.presence_of_element_located((By.XPATH, sel))
                    )
                    if el and el.is_displayed():
                        btn = el
                        break
                except WebDriverException:
                    continue
            if not btn:
                return False
            if reaction_already_set(btn):
                return False
            self.scroll_into_view(btn)
            return self.ui.click_with_fallback(btn, "Like (stream)")
        except WebDriverException:
            return False

    def comment_from_bar(
        self,
        bar,
        text: str,
        mention_author: bool = False,
        mention_position: str = "append",
        author_name: Optional[str] = None,
    ) -> bool:
        """Submit a comment using a post action bar and comment editor.

        WHY
          Leave a comment for the engage stream and the CLI one-shots, with
          optional author mention at the start or end. Each page step has a
          fallback, and a failure returns False instead of raising.

        Args
          bar: WebElement, the post action bar.
          text: str, the comment content to submit.
          mention_author: bool, whether to add an author mention.
          mention_position: str, "prepend" or "append" for the mention.
          author_name: Optional[str], an already extracted author name.

        Returns
          bool, True when the comment submit click reported success, False on
          any failed step.
        """
        if not text:
            return False
        try:
            opened = False
            for sel in EngageSelectors.COMMENT_BUTTONS:
                try:
                    btn = bar.find_element(By.XPATH, sel)
                    if btn and btn.is_displayed():
                        if self.ui.click_with_fallback(btn, "Comment (stream)"):
                            opened = True
                            break
                except WebDriverException:
                    continue
            if not opened:
                return False

            editor = None
            root = None
            try:
                root = self.find_post_root_for_bar(bar)
            except WebDriverException:
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
                except WebDriverException:
                    continue
            if not editor:
                return False

            self.ui.click_with_fallback(editor, "comment editor (stream)")

            base_text = text or ""
            author = None
            if mention_author:
                author = author_name
                if author is None:
                    try:
                        if root is None:
                            root = self.find_post_root_for_bar(bar)
                    except WebDriverException:
                        root = None
                    try:
                        author = self.extract_author_name(root) if root is not None else None
                    except WebDriverException:
                        author = None

            if mention_author and author and (mention_position or "append") == "prepend":
                logger.info("COMMENT_ORDER mention=prepend")
                try:
                    self.mentions.insert_mentions(
                        editor, [author], leading_space=False, force_start=True
                    )
                    try:
                        editor.send_keys(" ")
                    except WebDriverException:
                        pass
                except WebDriverException as e:
                    logger.warning(f"Error during prepend mention insertion: {e.msg}")

            if self.mentions.post_text_contains_inline_mentions(base_text):
                logger.info(f"Composing text with inline mentions: {base_text[:50]}...")
                if not self.mentions.compose_text_with_mentions(editor, base_text):
                    return False
            else:
                # Sanitize text for ChromeDriver (remove non-BMP characters like emojis)
                # to prevent "ChromeDriver only supports characters in the BMP" error.
                safe_text = self.mentions.sanitize_bmp(base_text)

                try:
                    # Re-focus editor to ensure keys reach it after mention logic
                    try:
                        self.ui.driver.execute_script("arguments[0].focus();", editor)
                        self.ui.pause(0.1, 0.3)
                    except WebDriverException:
                        pass

                    logger.info(f"Typing base comment text: {safe_text[:50]}...")
                    editor.send_keys(safe_text)
                except WebDriverException as e:
                    logger.warning(f"Standard send_keys failed for comment text: {e.msg}")
                    try:
                        # Use JS to APPEND the original text (including emojis)
                        # instead of overwriting the entire innerHTML (which removes mentions).
                        cleaned = base_text.replace("\n", "<br>")
                        self.ui.driver.execute_script(
                            """
                            const editor = arguments[0];
                            const html = arguments[1];
                            editor.focus();
                            // Attempt to insert at the end of the content
                            editor.insertAdjacentHTML('beforeend', html);
                            // Trigger input event so LinkedIn's editor detects the change
                            editor.dispatchEvent(new Event('input', { bubbles: true }));
                        """,
                            editor,
                            cleaned,
                        )
                        logger.info("Appended comment text via JavaScript fallback.")
                    except WebDriverException as js_e:
                        logger.error(f"Failed to append comment text via JS: {js_e}")
                        return False

            if mention_author and author and (mention_position or "append") == "append":
                logger.info("COMMENT_ORDER mention=append")
                try:
                    try:
                        self.ui.caret_to_end(editor)
                    except WebDriverException:
                        pass
                    try:
                        editor.send_keys(" ")
                    except WebDriverException:
                        pass
                    self.mentions.insert_mentions(
                        editor, [author], leading_space=True, force_end=True
                    )
                    try:
                        editor.send_keys(" ")
                    except WebDriverException:
                        pass
                except WebDriverException:
                    try:
                        editor.send_keys(f" @{author} ")
                    except WebDriverException:
                        pass
                try:
                    verified = self.mentions.verify_mention_entity(editor, author, timeout=2)
                except WebDriverException:
                    verified = False
                if not verified:
                    logger.warning(
                        f"Mention for {author} was not verified as an entity, "
                        "but leaving it as typed text to prevent duplicates."
                    )

            for sel in EngageSelectors.SUBMIT_COMMENT:
                try:
                    try:
                        logger.info("DISMISS before_submit: global search/typeahead overlay")
                        self.overlays.dismiss_global_search_overlay()
                    except WebDriverException:
                        pass
                    post_btn = WebDriverWait(self.ui.driver, 4).until(
                        EC.element_to_be_clickable((By.XPATH, sel))
                    )
                    try:
                        self.scroll_into_view(post_btn)
                    except WebDriverException:
                        pass
                    if self.ui.click_with_fallback(post_btn, "Submit comment (stream)"):
                        try:
                            root = self.find_post_root_for_bar(bar)
                            if root is None:
                                root = bar
                            self.ui.driver.execute_script(
                                "arguments[0].setAttribute('data-li-bot-commented','1');", root
                            )
                        except WebDriverException:
                            pass
                        try:
                            editor = (root if root is not None else bar).find_element(
                                By.XPATH, ".//div[@contenteditable='true']"
                            )
                            try:
                                editor.send_keys(Keys.ESCAPE)
                            except WebDriverException:
                                pass
                            try:
                                self.ui.driver.execute_script(
                                    "arguments[0].blur && arguments[0].blur();", editor
                                )
                            except WebDriverException:
                                pass
                        except WebDriverException:
                            pass
                        return True
                except WebDriverException:
                    continue
        except WebDriverException:
            return False
        return False

    def _repost_from_bar(
        self,
        bar,
        thoughts_text: str,
        mention_author: bool = False,
        mention_position: str = "append",
        author_name: Optional[str] = None,
    ) -> bool:
        """Submit a repost with commentary using a post action bar.

        WHY
          Share a post with our own thoughts, optionally mentioning the
          author. Each dropdown, editor and submit step falls back or returns
          False on failure, so a changed page does not raise.

        Args
          bar: WebElement, the post action bar.
          thoughts_text: str, the commentary to send with the repost.
          mention_author: bool, whether to add an author mention.
          mention_position: str, "prepend" or "append" for the mention.
          author_name: Optional[str], an already extracted author name.

        Returns
          bool, True when the repost submit click reported success, False on
          any failed step.
        """
        if not thoughts_text:
            return False

        try:
            repost_btn = None
            for sel in FeedActionSelectors.REPOST_BUTTONS:
                try:
                    btn = bar.find_element(By.XPATH, sel)
                    if btn and btn.is_displayed():
                        repost_btn = btn
                        break
                except WebDriverException:
                    continue
            if not repost_btn:
                return False
            if not self.ui.click_with_fallback(repost_btn, "Repost dropdown"):
                return False
            self.ui.pause(0.4, 0.8)

            dropdown_containers = []
            for xp in FeedActionSelectors.REPOST_DROPDOWN_CONTAINERS_SCOPED:
                try:
                    c = WebDriverWait(bar, 2).until(EC.presence_of_element_located((By.XPATH, xp)))
                    if c and c.is_displayed():
                        dropdown_containers.append(c)
                except WebDriverException:
                    continue
            if not dropdown_containers:
                try:
                    c = WebDriverWait(self.ui.driver, 2).until(
                        EC.presence_of_element_located(
                            (By.XPATH, FeedActionSelectors.REPOST_DROPDOWN_CONTAINERS_GLOBAL)
                        )
                    )
                    if c:
                        dropdown_containers.append(c)
                except WebDriverException:
                    pass

            text_candidates = FeedActionSelectors.REPOST_CANDIDATE_TEXTS

            option = None
            for container in dropdown_containers:
                tag_sets = FeedActionSelectors.REPOST_OPTION_TAGS
                for ts in tag_sets:
                    try:
                        nodes = container.find_elements(By.XPATH, ts)
                    except WebDriverException:
                        nodes = []
                    for n in nodes:
                        try:
                            if not n.is_displayed():
                                continue
                            txt = (n.text or "").strip().lower()
                            if not txt:
                                continue
                            for cand in text_candidates:
                                if cand in txt:
                                    option = n
                                    break
                            if option:
                                break
                        except WebDriverException:
                            continue
                    if option:
                        break
                if option:
                    break

            if not option:
                return False
            if not self.ui.click_with_fallback(option, "Repost with your thoughts"):
                return False
            self.ui.pause(0.6, 1.2)

            editor = None
            for xp in FeedActionSelectors.REPOST_EDITOR:
                try:
                    editor = WebDriverWait(self.ui.driver, 6).until(
                        EC.presence_of_element_located((By.XPATH, xp))
                    )
                    if editor and editor.is_displayed():
                        break
                except WebDriverException:
                    continue
            if not editor:
                return False
            self.ui.click_with_fallback(editor, "repost editor focus")

            # Sanitize for ChromeDriver BMP limitation
            safe_thoughts = self.mentions.sanitize_bmp(thoughts_text)

            try:
                editor.send_keys(safe_thoughts)
            except WebDriverException:
                try:
                    cleaned = thoughts_text.replace("\n", "<br>")
                    self.ui.driver.execute_script(
                        """
                        const editor = arguments[0];
                        const html = arguments[1];
                        editor.focus();
                        editor.insertAdjacentHTML('beforeend', html);
                        editor.dispatchEvent(new Event('input', { bubbles: true }));
                    """,
                        editor,
                        cleaned,
                    )
                except WebDriverException:
                    return False

            if mention_author:
                author = author_name
                if not author:
                    try:
                        root = self.find_post_root_for_bar(bar)
                        author = self.extract_author_name(root) if root else None
                    except WebDriverException:
                        pass
                if author:
                    if (mention_position or "append") == "prepend":
                        try:
                            self.ui.caret_to_start(editor)
                        except WebDriverException:
                            pass
                        self.mentions.insert_mentions(
                            editor, [author], leading_space=False, force_start=True
                        )
                        try:
                            editor.send_keys(" ")
                        except WebDriverException:
                            pass
                    else:
                        try:
                            self.ui.caret_to_end(editor)
                        except WebDriverException:
                            pass
                        try:
                            editor.send_keys(" ")
                        except WebDriverException:
                            pass
                        self.mentions.insert_mentions(
                            editor, [author], leading_space=True, force_end=True
                        )
                        try:
                            editor.send_keys(" ")
                        except WebDriverException:
                            pass

            for sel in FeedActionSelectors.SUBMIT_REPOST:
                try:
                    post_btn = WebDriverWait(self.ui.driver, 4).until(
                        EC.element_to_be_clickable((By.XPATH, sel))
                    )
                    if self.ui.click_with_fallback(post_btn, "Submit repost"):
                        return True
                except WebDriverException:
                    continue
            return False

        except WebDriverException:
            return False

    def scroll_into_view(self, el):
        """Scroll the viewport so the provided element becomes visible.

        WHY
          Selenium clicks fail when the element is offscreen, so centre it
          first. A scroll error is swallowed, because the click may still work.

        Args
          el: WebElement, the element to bring into view.

        MUTATIONS
          Scrolls the browser viewport.
        """
        try:
            self.ui.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except WebDriverException:
            pass
