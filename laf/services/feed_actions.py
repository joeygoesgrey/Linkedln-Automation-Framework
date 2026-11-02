"""Like, comment on and repost the first post in the LinkedIn feed.

WHY
  Give a quick one-post engagement action for smoke tests and CLI shortcuts,
  without running the full engage stream.
"""

import logging
from typing import Any, Callable, Optional

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from laf.config import Config
from laf.errors import AiError
from laf.selectors.feed import FeedActionSelectors

from ..ui import UiActions
from .engage_dom import EngageDomService
from .engage_utils import reaction_already_set
from .mentions import MentionService
from .overlays import OverlayService

logger = logging.getLogger(__name__)

class FeedService:
    """Act on the first visible feed post with like, comment or repost.

    WHY
      Let a caller engage one post with a single call, so quick checks and CLI
      flags do not need the full engage flow.
    """

    def __init__(
        self,
        ui: UiActions,
        config: Config,
        overlays: OverlayService,
        mentions: MentionService,
        engage_dom: EngageDomService,
    ) -> None:
        """
        WHY
          Give the quick feed actions the driver, settings, overlay cleanup,
          mention tools and post readers they need to act on the first post.

        Args
          ui: UiActions, the shared Selenium action helper.
          config: Config, the frozen runtime settings.
          overlays: OverlayService, used to clear dialogs over the feed.
          mentions: MentionService, used to insert mention entities.
          engage_dom: EngageDomService, used to read a post and its author.

        MUTATIONS
          Stores the driver, settings and the three partner services on the
          instance.
        """
        self.ui = ui
        self.config = config
        self.overlays = overlays
        self.mentions = mentions
        self.engage_dom = engage_dom

    def _goto_feed(self):
        """Load the feed and clear the overlays over it.

        WHY
          Every feed action needs the first post in view, so put the page there
          once instead of in each action.

        MUTATIONS
          Navigates the browser to the feed URL.
        """
        try:
            self.ui.driver.get(self.config.linkedin_feed_url)
        except WebDriverException:
            pass
        self.ui.pause(self.config.min_page_load_delay, self.config.max_page_load_delay)
        try:
            self.overlays.dismiss_overlays()
        except WebDriverException:
            pass

    def _first_action_bar(self):
        """Find the like, comment and repost bar of the top feed post.

        WHY
          All three quick actions hang off this bar, so finding it once gives
          them a common anchor.

        Returns
          Optional[WebElement], the first matching action bar, or None when no
          selector matched.
        """
        candidates = FeedActionSelectors.FIRST_ACTION_BAR
        for xp in candidates:
            try:
                bar = WebDriverWait(self.ui.driver, self.config.element_timeout).until(
                    EC.presence_of_element_located((By.XPATH, xp))
                )
                return bar
            except WebDriverException:
                continue
        return None

    def like_first_post(self):
        """Like the first feed post, or leave it when already liked.

        WHY
          Give the CLI a quick like action, and return False when the post or
          its like button cannot be found.

        Returns
          bool, True when the like is applied or was already there, False when
          the action bar or the like button is missing.
        """
        self._goto_feed()
        bar = self._first_action_bar()
        if not bar:
            logger.error("Could not find social action bar for first post")
            return False

        like_selectors = FeedActionSelectors.LIKE_BUTTONS

        btn = None
        for sel in like_selectors:
            try:
                el = bar.find_element(By.XPATH, sel)
                if el and el.is_displayed():
                    btn = el
                    break
            except WebDriverException:
                continue
        if not btn:
            logger.error("Like button not found on first post")
            return False

        if reaction_already_set(btn):
            logger.info("First post already liked; skipping")
            return True

        if not self.ui.click_with_fallback(btn, "Like (first post)"):
            return False
        self.ui.pause(0.5, 1.0)
        return True

    def _open_comment_editor_for_first_post(self) -> tuple[Optional[Any], Optional[Any]]:
        """Open the comment box on the first feed post.

        WHY
          Keep the action bar and editor discovery out of comment_first_post
          so it stays under the 60-line ceiling.

        Returns
          tuple[Optional[Any], Optional[Any]], (editor, bar) or (None, None).
        """
        bar = self._first_action_bar()
        if not bar:
            logger.error("Could not find social action bar for first post")
            return None, None

        comment_btn = None
        for sel in FeedActionSelectors.COMMENT_BUTTONS:
            try:
                el = bar.find_element(By.XPATH, sel)
                if el and el.is_displayed():
                    comment_btn = el
                    break
            except WebDriverException:
                continue
        if not comment_btn:
            logger.error("Comment button not found on first post")
            return None, None
        self.ui.click_with_fallback(comment_btn, "Comment (first post)")
        self.ui.pause(0.5, 1.0)

        editor = None
        for xp in FeedActionSelectors.COMMENT_EDITOR:
            try:
                editor = WebDriverWait(self.ui.driver, self.config.element_timeout).until(
                    EC.presence_of_element_located((By.XPATH, xp))
                )
                if editor and editor.is_displayed():
                    break
            except WebDriverException:
                editor = None
                continue
        if not editor:
            logger.error("Could not find comment editor for first post")
            return None, None

        try:
            self.ui.click_with_fallback(editor, "comment editor")
        except WebDriverException:
            pass
        return editor, bar

    def comment_first_post(
        self, text, mention_author: bool = False, mention_position: str = "append"
    ):
        """Comment on the first feed post, optionally mentioning its author.

        WHY
          Give a quick engage or smoke test path, and return False instead of
          raising when the post, editor or submit button cannot be reached.

        Args
          text: str, the comment body to submit.
          mention_author: bool, True to add the author's mention token.
          mention_position: str, "prepend" or "append" for the mention token.

        Returns
          bool, True when the comment was submitted, False when the text was
          empty or a step failed.

        MUTATIONS
          Types the comment into the page editor and submits it.
        """
        if not isinstance(text, str) or not text.strip():
            logger.error("comment_first_post requires non-empty text")
            return False

        self._goto_feed()
        editor, bar = self._open_comment_editor_for_first_post()
        if not editor:
            return False

        # If requested, append/prepend the author's mention token
        if mention_author:
            try:
                root = self.engage_dom.find_post_root_for_bar(bar)
                author = (
                    self.engage_dom.extract_author_name(root) if root is not None else None
                )
            except WebDriverException:
                author = None
            if author:
                token = f"@{{{author}}}"
                if token not in (text or ""):
                    if (mention_position or "append") == "prepend":
                        text = f"{token} {text}" if text else token
                    else:
                        text = f"{text} {token}" if text else token

        # Support inline mention tokens '@{Display Name}' in comment text
        if self.mentions.post_text_contains_inline_mentions(text):
            if not self.mentions.compose_text_with_mentions(editor, text):
                logger.error("Failed composing comment with mentions")
                return False
        else:
            try:
                editor.send_keys(text)
            except WebDriverException:
                # JS fallback
                try:
                    cleaned = text.replace("\n", "<br>")
                    self.ui.driver.execute_script(
                        "arguments[0].innerHTML = arguments[1];", editor, cleaned
                    )
                except WebDriverException as e:
                    logger.error(f"Failed to type comment: {e.msg}")
                    return False
        self.ui.pause(0.4, 0.8)

        # Click Post on the comment box
        post_btn_selectors = FeedActionSelectors.SUBMIT_COMMENT
        posted = False
        for sel in post_btn_selectors:
            try:
                btn = WebDriverWait(self.ui.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, sel))
                )
                if self.ui.click_with_fallback(btn, "Submit comment"):
                    posted = True
                    break
            except WebDriverException:
                continue
        if not posted:
            # Keyboard Enter as a last resort
            try:
                editor.send_keys(Keys.ENTER)
                posted = True
            except WebDriverException:
                pass

        self.ui.pause(0.8, 1.5)
        return posted

    def _generate_repost_thoughts(
        self, thoughts_text, comment_generator, bar
    ) -> Optional[str]:
        """Return repost thoughts, generating them via AI if needed.

        WHY
          Keep the thoughts generation logic out of repost_first_post.

        Returns
          Optional[str], the thoughts text, or None when none could be
          obtained.
        """
        if thoughts_text and thoughts_text.strip():
            return thoughts_text
        if not comment_generator:
            logger.error(
                "repost_first_post requires non-empty thoughts_text "
                "or a successful AI generation"
            )
            return None
        try:
            root = self.engage_dom.find_post_root_for_bar(bar)
        except WebDriverException as e:
            logger.error(f"Failed to find post root for repost: {e.msg}")
            return None
        try:
            return comment_generator(root)
        except (AiError, WebDriverException) as e:
            logger.error(f"Failed to generate AI thoughts: {e}")
            return None

    def _open_and_select_repost_option(self, bar) -> bool:
        """Open the repost dropdown and select 'Repost with your thoughts'.

        WHY
          Keep the dropdown + option selection out of repost_first_post.

        Returns
          bool, True when the option was clicked.
        """
        repost_btn = None
        for sel in FeedActionSelectors.REPOST_BUTTONS:
            try:
                el = bar.find_element(By.XPATH, sel)
                if el and el.is_displayed():
                    repost_btn = el
                    break
            except WebDriverException:
                continue
        if not repost_btn:
            logger.error("Repost button not found on first post")
            return False
        if not self.ui.click_with_fallback(repost_btn, "Repost dropdown"):
            return False
        self.ui.pause(0.4, 0.8)

        containers = []
        for xp in FeedActionSelectors.REPOST_DROPDOWN_CONTAINERS_SCOPED:
            try:
                c = WebDriverWait(bar, 2).until(EC.presence_of_element_located((By.XPATH, xp)))
                if c and c.is_displayed():
                    containers.append(c)
            except WebDriverException:
                continue
        if not containers:
            try:
                c = WebDriverWait(self.ui.driver, 2).until(
                    EC.presence_of_element_located(
                        (By.XPATH, FeedActionSelectors.REPOST_DROPDOWN_CONTAINERS_GLOBAL)
                    )
                )
                if c:
                    containers.append(c)
            except WebDriverException:
                pass

        option = self._scan_repost_dropdowns(containers)
        if not option:
            option = self._scan_repost_globally()
        if not option:
            logger.error("'Repost with thoughts' option not found")
            return False
        if not self.ui.click_with_fallback(option, "Repost with your thoughts"):
            return False
        self.ui.pause(0.6, 1.2)
        return True

    def _scan_repost_dropdowns(self, containers) -> Optional[Any]:
        """Scan dropdown containers for a 'Repost with thoughts' option.

        Returns
          Optional[Any], the option element, or None.
        """
        text_candidates = FeedActionSelectors.REPOST_CANDIDATE_TEXTS
        for container in containers:
            for ts in FeedActionSelectors.REPOST_OPTION_TAGS:
                try:
                    nodes = container.find_elements(By.XPATH, ts)
                except WebDriverException:
                    continue
                for n in nodes:
                    try:
                        if not n.is_displayed():
                            continue
                        txt = (n.text or "").strip().lower()
                        if not txt:
                            continue
                        for cand in text_candidates:
                            if cand in txt:
                                try:
                                    return n.find_element(
                                        By.XPATH, FeedActionSelectors.REPOST_OPTION_ROW
                                    )
                                except WebDriverException:
                                    return n
                    except WebDriverException:
                        continue
        return None

    def _scan_repost_globally(self) -> Optional[Any]:
        """Search the whole page for a 'Repost with thoughts' option.

        Returns
          Optional[Any], the option element, or None.
        """
        for cand in FeedActionSelectors.REPOST_CANDIDATE_TEXTS:
            xp = FeedActionSelectors.REPOST_GLOBAL_OPTION_XPATH_TEMPLATE.format(cand=cand)
            try:
                nodes = self.ui.driver.find_elements(By.XPATH, xp)
                for n in nodes:
                    try:
                        if n.is_displayed():
                            return n
                    except WebDriverException:
                        continue
            except WebDriverException:
                continue
        return None

    def _find_and_focus_editor(self) -> Optional[Any]:
        """Find the repost editor and focus it.

        Returns
          Optional[Any], the editor element, or None.
        """
        for xp in FeedActionSelectors.REPOST_EDITOR:
            try:
                editor = WebDriverWait(self.ui.driver, 6).until(
                    EC.presence_of_element_located((By.XPATH, xp))
                )
                if editor and editor.is_displayed():
                    try:
                        self.ui.click_with_fallback(editor, "repost editor focus")
                    except WebDriverException:
                        pass
                    return editor
            except WebDriverException:
                continue
        logger.error("Could not find repost thoughts editor")
        return None

    def _type_into_editor(self, editor, text: str) -> bool:
        """Type text into an editor, with JS fallback.

        Returns
          bool, True when the text was typed or inserted.
        """
        try:
            editor.send_keys(text)
        except WebDriverException:
            try:
                cleaned = text.replace("\n", "<br>")
                self.ui.driver.execute_script(
                    "arguments[0].innerHTML = arguments[1];", editor, cleaned
                )
            except WebDriverException as e:
                logger.error(f"Failed to type thoughts text: {e.msg}")
                return False
        return True

    def _insert_author_mention(self, editor, bar, mention_author, mention_position) -> None:
        """Insert an author mention into the editor.

        MUTATIONS
          Types text into the editor.
        """
        if not mention_author:
            return
        author = None
        try:
            root = self.engage_dom.find_post_root_for_bar(bar)
            author = self.engage_dom.extract_author_name(root) if root else None
        except WebDriverException:
            pass
        if not author:
            return
        try:
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
        except WebDriverException:
            try:
                if (mention_position or "append") == "prepend":
                    editor.send_keys(f"@{author} ")
                else:
                    self.ui.caret_to_end(editor)
                    editor.send_keys(f" @{author} ")
            except WebDriverException:
                pass

    def _find_and_click_submit(self) -> bool:
        """Find the Post/Share button and click it.

        Returns
          bool, True when the button was clicked.
        """
        for sel in FeedActionSelectors.SUBMIT_REPOST:
            try:
                btn = WebDriverWait(self.ui.driver, 6).until(
                    EC.element_to_be_clickable((By.XPATH, sel))
                )
                if self.ui.click_with_fallback(btn, "Submit repost"):
                    self.ui.pause(1.0, 1.8)
                    return True
            except WebDriverException:
                continue
        logger.error("Could not find Post/Share button for repost")
        return False

    def repost_first_post(
        self,
        thoughts_text: Optional[str] = None,
        comment_generator: Optional[Callable[[Any], Optional[str]]] = None,
        mention_author: bool = False,
        mention_position: str = "append",
    ) -> bool:
        """Repost the first feed post with supplied or generated thoughts.

        WHY
          Share the first post with commentary in one call, and return False
          when the dropdown, editor or submit button cannot be reached.

        Args
          thoughts_text: Optional[str], the commentary, or None to generate it.
          comment_generator: Optional[Callable[[Any], Optional[str]]], called
            with the post when thoughts_text is empty, or None.
          mention_author: bool, True to mention the original author.
          mention_position: str, "prepend" or "append" for the mention token.

        Returns
          bool, True when the repost was submitted, False when no thoughts,
          option, editor or submit button was available.

        MUTATIONS
          Types the thoughts into the repost editor and submits the share.
        """
        self._goto_feed()
        bar = self._first_action_bar()
        if not bar:
            logger.error("Could not find social action bar for first post (repost)")
            return False

        thoughts_text = self._generate_repost_thoughts(thoughts_text, comment_generator, bar)
        if not thoughts_text:
            return False

        if not self._open_and_select_repost_option(bar):
            return False

        editor = self._find_and_focus_editor()
        if not editor:
            return False

        if not self._type_into_editor(editor, thoughts_text):
            return False

        self._insert_author_mention(editor, bar, mention_author, mention_position)

        return self._find_and_click_submit()
