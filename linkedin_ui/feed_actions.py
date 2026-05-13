"""
Feed actions: like and comment on posts in the home feed.

Why:
    Provide simple helpers to react (Like) and add a comment to the first
    visible post, enabling lightweight engagement automation.

When:
    After logging in, from the home feed. These helpers navigate to the feed,
    dismiss overlays, locate the first post's social action bar, and act.

How:
    - Like: find the Like/React button and click (skip if already liked).
    - Comment: open the comment box, type text, and click the Post button.
"""

import logging
from typing import Optional, Callable, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import config
from ui_selectors import FeedActionSelectors


class FeedActionsMixin:
    """Provide one-off like/comment/repost helpers for the feed.

    Why:
        Support CLI shortcuts and testing scenarios without invoking the full engage stream.

    When:
        Mixed into :class:`LinkedInInteraction` to support quick feed actions.

    How:
        Offers methods that navigate to the feed, locate the first post, and perform targeted social actions.
    """
    def _goto_feed(self):
        """Navigate to the home feed and clear obstructive overlays.

        Why:
            Feed actions require being on the main feed with minimal obstructions.

        When:
            Called at the start of like, comment, and repost helpers.

        How:
            Loads the feed URL, waits for load delays, and dismisses overlays if
            present.

        Returns:
            None
        """
        try:
            self.driver.get(config.LINKEDIN_FEED_URL)
        except Exception:
            pass
        self.random_delay(config.MIN_PAGE_LOAD_DELAY, config.MAX_PAGE_LOAD_DELAY)
        try:
            self.dismiss_overlays()
        except Exception:
            pass

    def _first_action_bar(self):
        """Locate the social action bar for the top-most feed post.

        Why:
            Feed actions (like/comment/repost) need this element to find buttons.

        When:
            Immediately after navigating to the feed before performing actions.

        How:
            Iterates through XPath selectors targeting the first visible action
            bar and returns the first match.

        Returns:
            WebElement | None: Action bar element if found, else ``None``.
        """
        candidates = FeedActionSelectors.FIRST_ACTION_BAR
        for xp in candidates:
            try:
                bar = WebDriverWait(self.driver, config.ELEMENT_TIMEOUT).until(
                    EC.presence_of_element_located((By.XPATH, xp))
                )
                return bar
            except Exception:
                continue
        return None

    def like_first_post(self):
        """Like the first visible post in the feed if not already liked.

        Why:
            Provides a quick engagement action for CLI shortcuts.

        When:
            Triggered by the `--like-first` flag.

        How:
            Navigates to the feed, locates the first action bar, finds the like
            button, and clicks it unless it is already pressed.

        Returns:
            bool: ``True`` when the like is applied or already present, ``False``
            when the action bar or button cannot be found.
        """
        self._goto_feed()
        bar = self._first_action_bar()
        if not bar:
            logging.error("Could not find social action bar for first post")
            return False

        like_selectors = FeedActionSelectors.LIKE_BUTTONS

        btn = None
        for sel in like_selectors:
            try:
                el = bar.find_element(By.XPATH, sel)
                if el and el.is_displayed():
                    btn = el
                    break
            except Exception:
                continue
        if not btn:
            logging.error("Like button not found on first post")
            return False

        try:
            pressed = (btn.get_attribute("aria-pressed") or "").lower() == "true"
        except Exception:
            pressed = False
        if pressed:
            logging.info("First post already liked; skipping")
            return True

        if not self._click_element_with_fallback(btn, "Like (first post)"):
            return False
        self.random_delay(0.5, 1.0)
        return True

    def comment_first_post(self, text, mention_author: bool = False, mention_position: str = 'append'):
        """Leave a comment on the first feed post, optionally mentioning the author.

        Why:
            Handy for quick engagement or smoke tests without running the full
            engage stream.

        When:
            Triggered via the `--comment-first` CLI flag.

        How:
            Navigates to the feed, opens the comment editor, optionally inserts
            mention tokens (inline or derived), types the comment, and submits
            with fallbacks.

        Args:
            text (str): Comment content to submit.
            mention_author (bool): Whether to add the author's mention token.
            mention_position (str): Placement for the mention (`'prepend'` or `'append'`).

        Returns:
            bool: ``True`` when submission appears to succeed, ``False`` otherwise.
        """
        if not isinstance(text, str) or not text.strip():
            logging.error("comment_first_post requires non-empty text")
            return False

        self._goto_feed()
        bar = self._first_action_bar()
        if not bar:
            logging.error("Could not find social action bar for first post")
            return False

        # Open the comment box
        comment_btn_selectors = FeedActionSelectors.COMMENT_BUTTONS
        comment_btn = None
        for sel in comment_btn_selectors:
            try:
                el = bar.find_element(By.XPATH, sel)
                if el and el.is_displayed():
                    comment_btn = el
                    break
            except Exception:
                continue
        if not comment_btn:
            logging.error("Comment button not found on first post")
            return False
        self._click_element_with_fallback(comment_btn, "Comment (first post)")
        self.random_delay(0.5, 1.0)

        # Find the inline comment editor near the first post
        editor_selectors = FeedActionSelectors.COMMENT_EDITOR
        editor = None
        for xp in editor_selectors:
            try:
                editor = WebDriverWait(self.driver, config.ELEMENT_TIMEOUT).until(
                    EC.presence_of_element_located((By.XPATH, xp))
                )
                if editor and editor.is_displayed():
                    break
            except Exception:
                editor = None
                continue
        if not editor:
            logging.error("Could not find comment editor for first post")
            return False

        try:
            self._click_element_with_fallback(editor, "comment editor")
        except Exception:
            pass

        # If requested, append/prepend the author's mention token
        if mention_author:
            try:
                root = self._find_post_root_for_bar(bar)
                author = self._extract_author_name(root) if root is not None else None
            except Exception:
                author = None
            if author:
                token = f"@{{{author}}}"
                if token not in (text or ""):
                    if (mention_position or 'append') == 'prepend':
                        text = f"{token} {text}" if text else token
                    else:
                        text = f"{text} {token}" if text else token

        # Support inline mention tokens '@{Display Name}' in comment text
        if hasattr(self, "_post_text_contains_inline_mentions") and \
           self._post_text_contains_inline_mentions(text):
            if not self._compose_text_with_mentions(editor, text):
                logging.error("Failed composing comment with mentions")
                return False
        else:
            try:
                editor.send_keys(text)
            except Exception:
                # JS fallback
                try:
                    cleaned = text.replace('\n', '<br>')
                    self.driver.execute_script("arguments[0].innerHTML = arguments[1];", editor, cleaned)
                except Exception as e:
                    logging.error(f"Failed to type comment: {e}")
                    return False
        self.random_delay(0.4, 0.8)

        # Click Post on the comment box
        post_btn_selectors = FeedActionSelectors.SUBMIT_COMMENT
        posted = False
        for sel in post_btn_selectors:
            try:
                btn = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, sel))
                )
                if self._click_element_with_fallback(btn, "Submit comment"):
                    posted = True
                    break
            except Exception:
                continue
        if not posted:
            # Keyboard Enter as a last resort
            try:
                editor.send_keys(Keys.ENTER)
                posted = True
            except Exception:
                pass

        self.random_delay(0.8, 1.5)
        return posted

    def repost_first_post(
        self, 
        thoughts_text: Optional[str] = None, 
        comment_generator: Optional[Callable[[Any], Optional[str]]] = None,
        mention_author: bool = False, 
        mention_position: str = 'append'
    ) -> bool:
        """Share the first feed post with personalised thoughts.

        Why:
            Streamlines reposting with commentary for quick amplification.

        When:
            Invoked via the `--repost-first` flag.

        How:
            Navigates to the feed, opens the repost dropdown, selects "Repost
            with your thoughts", types the supplied text (optionally inserting
            an author mention), and submits the share.

        Args:
            thoughts_text (str | None): Commentary to accompany the repost.
            comment_generator (Callable | None): Optional AI generator.
            mention_author (bool): Whether to mention the original author.
            mention_position (str): Placement for the mention token.

        Returns:
            bool: ``True`` when the repost workflow appears successful, else ``False``.
        """
        self._goto_feed()
        bar = self._first_action_bar()
        if not bar:
            logging.error("Could not find social action bar for first post (repost)")
            return False

        if not thoughts_text or not thoughts_text.strip():
            if comment_generator:
                try:
                    root = self._find_post_root_for_bar(bar)
                    thoughts_text = comment_generator(root)
                except Exception as e:
                    logging.error(f"Failed to generate AI thoughts: {e}")
                    
        if not thoughts_text or not thoughts_text.strip():
            logging.error("repost_first_post requires non-empty thoughts_text or a successful AI generation")
            return False

        # Open the Repost dropdown
        repost_btn = None
        for sel in FeedActionSelectors.REPOST_BUTTONS:
            try:
                el = bar.find_element(By.XPATH, sel)
                if el and el.is_displayed():
                    repost_btn = el
                    break
            except Exception:
                continue
        if not repost_btn:
            logging.error("Repost button not found on first post")
            return False
        if not self._click_element_with_fallback(repost_btn, "Repost dropdown"):
            return False
        self.random_delay(0.4, 0.8)

        # Choose 'Repost with your thoughts' (robust search)
        option = None
        # First, try to scope to a dropdown content element near the bar
        dropdown_containers = []
        for xp in FeedActionSelectors.REPOST_DROPDOWN_CONTAINERS_SCOPED:
            try:
                c = WebDriverWait(bar, 2).until(EC.presence_of_element_located((By.XPATH, xp)))
                if c and c.is_displayed():
                    dropdown_containers.append(c)
            except Exception:
                continue
        if not dropdown_containers:
            # Global fallback (dropdown content may not be under bar)
            try:
                c = WebDriverWait(self.driver, 2).until(
                    EC.presence_of_element_located((By.XPATH, FeedActionSelectors.REPOST_DROPDOWN_CONTAINERS_GLOBAL))
                )
                if c:
                    dropdown_containers.append(c)
            except Exception:
                pass

        # Candidate text patterns (case-insensitive)
        text_candidates = FeedActionSelectors.REPOST_CANDIDATE_TEXTS

        def _find_option_in(container):
            """Search a dropdown container for the repost-with-thoughts option.

            Why:
                The option may appear under various tags; abstracting the search
                keeps the parent logic readable.

            When:
                Called after opening the repost dropdown for each candidate container.

            How:
                Iterates through common tags, checks visibility, normalises text,
                and compares against known label variants.

            Args:
                container (WebElement): Dropdown container to inspect.

            Returns:
                WebElement | None: Matching option element if found.
            """
            # Try common clickable tags first
            tag_sets = FeedActionSelectors.REPOST_OPTION_TAGS
            for ts in tag_sets:
                try:
                    nodes = container.find_elements(By.XPATH, ts)
                except Exception:
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
                                return n
                    except Exception:
                        continue
            return None

        for container in dropdown_containers:
            option = _find_option_in(container)
            if option:
                break
        if not option:
            # Global catch-all search for any visible node with the text
            try:
                option = None
                for cand in text_candidates:
                    xp = FeedActionSelectors.REPOST_GLOBAL_OPTION_XPATH_TEMPLATE.format(cand=cand)
                    nodes = self.driver.find_elements(By.XPATH, xp)
                    for n in nodes:
                        try:
                            if n.is_displayed():
                                option = n
                                break
                        except Exception:
                            continue
                    if option:
                        break
            except Exception:
                option = None
        if not option:
            logging.error("'Repost with your thoughts' option not found")
            return False
        if not self._click_element_with_fallback(option, "Repost with your thoughts"):
            return False
        self.random_delay(0.6, 1.2)

        # Find the repost editor
        editor = None
        editor_xpaths = FeedActionSelectors.REPOST_EDITOR
        for xp in editor_xpaths:
            try:
                editor = WebDriverWait(self.driver, 6).until(
                    EC.presence_of_element_located((By.XPATH, xp))
                )
                if editor and editor.is_displayed():
                    break
            except Exception:
                continue
        if not editor:
            logging.error("Could not find repost thoughts editor")
            return False
        try:
            self._click_element_with_fallback(editor, "repost editor focus")
        except Exception:
            pass

        # Compose base text
        try:
            editor.send_keys(thoughts_text)
        except Exception:
            try:
                cleaned = thoughts_text.replace('\n', '<br>')
                self.driver.execute_script("arguments[0].innerHTML = arguments[1];", editor, cleaned)
            except Exception as e:
                logging.error(f"Failed to type thoughts text: {e}")
                return False

        # Mention author appended by default (or prepend if specified)
        if mention_author:
            author = None
            try:
                root = self._find_post_root_for_bar(bar)
                author = self._extract_author_name(root) if root is not None else None
            except Exception:
                author = None
            if author:
                try:
                    if (mention_position or 'append') == 'prepend':
                        # Move caret to start and insert
                        try:
                            self._move_caret_to_start(editor)
                        except Exception:
                            pass
                        self._insert_mentions(editor, [author], leading_space=False, force_start=True)
                        try:
                            editor.send_keys(" ")
                        except Exception:
                            pass
                    else:
                        # Append at end
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
                        if (mention_position or 'append') == 'prepend':
                            editor.send_keys(f"@{author} ")
                        else:
                            self._move_caret_to_end(editor)
                            editor.send_keys(f" @{author} ")
                    except Exception:
                        pass

        # Click Post/Share
        post_btn = None
        for sel in FeedActionSelectors.SUBMIT_REPOST:
            try:
                post_btn = WebDriverWait(self.driver, 6).until(
                    EC.element_to_be_clickable((By.XPATH, sel))
                )
                break
            except Exception:
                continue
        if not post_btn:
            logging.error("Could not find Post/Share button for repost")
            return False
        if not self._click_element_with_fallback(post_btn, "Submit repost"):
            return False

        self.random_delay(1.0, 1.8)
        return True
