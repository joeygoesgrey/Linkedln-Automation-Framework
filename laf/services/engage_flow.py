"""Execution logic coordinating the engage-stream iteration loop.

WHY
  Keep orchestration out of the DOM helpers, so the loop that decides what to
  do with each post can be read and tested on its own.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

from laf.config import Config
from laf.errors import AiError
from laf.selectors.engage import EngageSelectors

from .engage_types import CommentPlan, EngageContext
from .engage_utils import choose_ai_perspective, pause_between, summarize_post_text

logger = logging.getLogger(__name__)

class EngageExecutor:
    """Drive the engage stream using the service objects it needs.

    WHY
      Run one feed session: load history, open the feed, then decide and act
      on each visible post until the limit or the user stops it.

    MUTATIONS
      The run changes the stored context: counters, processed and acted sets,
      and the persisted state file.
    """

    def __init__(
        self,
        ui,
        engage_dom,
        overlays,
        engage_service,
        config: Config,
        context: EngageContext,
    ) -> None:
        """Store the partner services, settings and runtime context.

        WHY
          Give the executor every partner it needs up front, so each helper
          call during the run needs no extra wiring.

        Args
          ui: UiActions, the shared Selenium action helper.
          engage_dom: EngageDomService, reads and acts on feed posts.
          overlays: OverlayService, clears dialogs over the feed.
          engage_service: EngageService, owns pacing and like state.
          config: Config, the frozen runtime settings.
          context: EngageContext, configuration and mutable state for the run.

        MUTATIONS
          Stores the partners and the context on the instance.
        """
        self.ui = ui
        self.engage_dom = engage_dom
        self.overlays = overlays
        self.engage_service = engage_service
        self.config = config
        self.ctx = context

    # Public entry points -------------------------------------------------

    def prepare_state(self) -> None:
        """Load and prune engage-state history before running.

        WHY
          Keep the dedupe cache useful by dropping comment URNs older than the
          seven day TTL, so old posts may be commented again.

        MUTATIONS
          Writes the pruned state to ``ctx.state`` and adds the kept URNs to
          ``ctx.commented_urns``.
        """
        state = self.engage_dom.load_engage_state()
        timestamps = state.get("commented_urns_ts") or {}
        kept = {}
        now = time.time()
        ttl_days = 7
        for urn, ts in list(timestamps.items()):
            try:
                if now - float(ts) < ttl_days * 86400:
                    kept[urn] = float(ts)
            except (ValueError, TypeError):
                continue
        state["commented_urns_ts"] = kept
        self.ctx.state = state
        self.ctx.commented_urns.update(kept.keys())

    def navigate_to_feed(self) -> None:
        """Open the LinkedIn feed and clear overlays before engagement.

        WHY
          Leave the viewport ready to scroll and click. A failed load or a
          failed overlay dismissal is swallowed, so a popup cannot stop the run.

        MUTATIONS
          Navigates the browser to the feed URL and dismisses page overlays.
        """
        try:
            self.ui.driver.get(self.config.linkedin_feed_url)
        except WebDriverException:
            pass
        pause_between(self.config.min_page_load_delay, self.config.max_page_load_delay)
        try:
            self.overlays.dismiss_overlays()
        except WebDriverException:
            pass

    def run(self) -> bool:
        """Execute the engagement loop until the limit is reached.

        WHY
          Keep acting on visible posts and loading more, so a finite run reaches
          its action cap and an infinite run continues until the user stops it.

        Returns
          bool, True when the loop exits. The body has no False path, because a
          cancellation is handled by the caller.
        """
        while True:
            if not self.ctx.infinite and self.ctx.actions_done >= self.ctx.max_actions:
                break

            posts = self.engage_dom.find_visible_posts(limit=12)
            if not posts:
                if self._handle_empty_viewport():
                    break
                continue

            made_progress = False
            for post in posts:
                if not self.ctx.infinite and self.ctx.actions_done >= self.ctx.max_actions:
                    break
                if self._process_post(post):
                    made_progress = True

            if (
                self.ctx.infinite or self.ctx.actions_done < self.ctx.max_actions
            ) and not made_progress:
                self._handle_no_progress()

        logger.info(f"Engage stream finished (actions={self.ctx.actions_done})")
        return True

    # Internals -----------------------------------------------------------

    def _handle_empty_viewport(self) -> bool:
        """React to a viewport with no detectable posts.

        WHY
          Load more content when the viewport looks empty, and stop a finite run
          after too many empty scrolls instead of looping forever.

        Returns
          bool, True when the executor should stop, False when it should try
          another scroll.

        MUTATIONS
          Scrolls the feed, possibly forces extra loading, and increments
          ``ctx.page_scrolls``.
        """
        logger.info("SCROLL_LOOP no_posts_found -> scroll_feed")

        prev_keys = self.engage_dom.visible_post_keys(limit=12)
        self.engage_dom.scroll_feed(self.ctx.scroll_wait_min, self.ctx.scroll_wait_max)
        now_keys = self.engage_dom.visible_post_keys(limit=12)
        if set(now_keys) == set(prev_keys):
            self.engage_dom.aggressive_load_more(
                prev_keys,
                tries=3,
                wait_min=self.ctx.scroll_wait_min,
                wait_max=self.ctx.scroll_wait_max,
            )

        self.ctx.page_scrolls += 1
        if not self.ctx.infinite and self.ctx.page_scrolls > 20:
            logger.info("No more posts found after many scrolls; stopping")
            return True
        return False

    def _handle_no_progress(self) -> None:
        """Respond to a viewport pass that yielded no new actions.

        WHY
          Avoid getting stuck on posts already handled, by scrolling and forcing
          more content when the visible keys do not change.

        MUTATIONS
          Scrolls the feed and may force extra loading.
        """
        logger.info("SCROLL_LOOP no_progress_in_viewport -> scroll_feed")
        prev_keys = self.engage_dom.visible_post_keys(limit=16)
        self.engage_dom.scroll_feed(self.ctx.scroll_wait_min, self.ctx.scroll_wait_max)
        now_keys = self.engage_dom.visible_post_keys(limit=16)
        if set(now_keys) == set(prev_keys):
            self.engage_dom.aggressive_load_more(
                prev_keys,
                tries=3,
                wait_min=self.ctx.scroll_wait_min,
                wait_max=self.ctx.scroll_wait_max,
            )

    def _process_post(self, post_root) -> bool:
        """Evaluate a single post for commenting and/or liking.

        WHY
          Make the decision for one post in one place: skip it when it is a
          duplicate or disallowed, otherwise comment and/or like it as the
          context asks.

        Args
          post_root: WebElement, the post container from the visible list.

        Returns
          bool, True when at least one action happened, False otherwise.

        MUTATIONS
          Adds the post keys to the processed sets, and may update the action
          counters, liked and commented sets through the comment and like paths.
        """
        progress = False
        try:
            self.engage_dom.scroll_into_view(post_root)
            self.engage_service.action_pause(self.ctx, 0.3, 0.7)
        except WebDriverException:
            pass

        urn = self.engage_dom.extract_post_urn(post_root)
        data_id = self.engage_dom.extract_data_id(post_root)
        text_key = self.engage_dom.post_text_key(post_root)
        key = self.engage_dom.post_dedupe_key(post_root, urn)
        logger.info(
            f"ENGAGE_KEYS urn={urn or 'none'} data_id={data_id or 'none'} key={key[:8]} "
            f"text_key={text_key[:8] if text_key else 'none'}"
        )

        if self._should_skip_post(post_root, key, text_key, data_id):
            return False

        self.ctx.processed.add(key)
        if text_key:
            self.ctx.processed_text_keys.add(text_key)
        if data_id:
            self.ctx.processed_ids.add(data_id)

        bar = self._locate_action_bar(post_root)
        if not bar:
            return False

        if self.ctx.mode in ("comment", "both") and self._can_take_action():
            plan = self._prepare_comment_plan(post_root, bar, urn, key)
            if plan.skip_reason:
                return False
            if plan.text and self._perform_comment(bar, plan, post_root, key, urn, data_id):
                progress = True
                self._maybe_like_after_comment(bar, post_root, key, urn)

        if self.ctx.mode == "like" and self._can_take_action():
            if self._attempt_like_only(bar, post_root, key, urn):
                progress = True

        return progress

    def _should_skip_post(
        self, post_root, key: str, text_key: Optional[str], data_id: Optional[str]
    ) -> bool:
        """Decide whether to skip a post based on dedupe and filters.

        WHY
          Stop a second action on the same post and skip promoted content when
          the run does not allow it, so the session does not look automated.

        Args
          post_root: WebElement, the post under consideration.
          key: str, the primary dedupe key from the caller.
          text_key: Optional[str], the text based dedupe key.
          data_id: Optional[str], the extra dedupe identifier.

        Returns
          bool, True when the post should be skipped.

        MUTATIONS
          On a DOM mark or a promoted post, adds the keys to the processed sets.
        """
        if key in self.ctx.processed:
            logger.info("ENGAGE_SKIP reason=processed_key")
            return True
        if text_key and text_key in self.ctx.processed_text_keys:
            logger.info("ENGAGE_SKIP reason=processed_text_key")
            return True
        if data_id and data_id in self.ctx.processed_ids:
            logger.info("ENGAGE_SKIP reason=processed_data_id")
            return True

        try:
            marker = self.ui.driver.execute_script(
                "return arguments[0].getAttribute('data-li-bot-commented');",
                post_root,
            )
            if str(marker).strip() == "1":
                self.ctx.processed.add(key)
                if text_key:
                    self.ctx.processed_text_keys.add(text_key)
                if data_id:
                    self.ctx.processed_ids.add(data_id)
                logger.info("ENGAGE_SKIP reason=dom_mark_commented")
                return True
        except WebDriverException:
            pass

        if not self.ctx.include_promoted and self.engage_dom.is_promoted_post(post_root):
            logger.debug(f"Skipping promoted post (urn={key or 'unknown'})")
            self.ctx.processed.add(key)
            if text_key:
                self.ctx.processed_text_keys.add(text_key)
            logger.info("ENGAGE_SKIP reason=promoted")
            return True

        return False

    def _locate_action_bar(self, post_root):
        """Return the social action bar associated with a post.

        WHY
          Give the like and comment helpers the container that holds the
          buttons, or None when the page shape is different.

        Args
          post_root: WebElement, the post container from the visible list.

        Returns
          Optional[WebElement], the action bar, or None when not found.
        """
        try:
            return post_root.find_element(By.XPATH, EngageSelectors.ACTION_BAR)
        except WebDriverException:
            return None

    def _prepare_comment_plan(
        self, post_root, bar, urn: Optional[str], key: str
    ) -> CommentPlan:
        """Determine whether to comment on a post and how.

        WHY
          Decide the comment text, perspective and skip reason before any text
          is typed, so an already handled post never gets a second comment.

        Args
          post_root: WebElement, the post container.
          bar: WebElement, the action bar for the post.
          urn: Optional[str], the post URN when one was found.
          key: str, the primary dedupe key for the post.

        Returns
          CommentPlan, the chosen text and perspective, or the reason to skip.

        MUTATIONS
          When an existing or similar comment is found, adds the URN to
          ``ctx.commented_urns``.
        """
        plan = CommentPlan(text=None, perspective=None, author_name=None, skip_reason=None)

        if self.ctx.mode not in ("comment", "both"):
            plan.skip_reason = "comments_disabled"
            return plan

        if self.ctx.mention_author:
            try:
                plan.author_name = self.engage_dom.extract_author_name(post_root)
            except WebDriverException:
                plan.author_name = None

        if self.ctx.mode == "comment":
            try:
                if self.engage_service.is_liked(self.ctx, urn, key):
                    logger.info("Skipping comment: post already liked (gate, comment-only mode)")
                    plan.skip_reason = "already_liked"
                    return plan
            except TypeError:
                pass

        if urn and urn in self.ctx.commented_urns:
            logger.info("Skipping comment: URN already commented this run")
            plan.skip_reason = "urn_already_commented"
            return plan

        plan.text, plan.perspective = self._determine_comment_text(post_root)

        if not plan.text:
            logger.info("ENGAGE_SKIP reason=no_comment_text_available")
            plan.skip_reason = "no_comment_text"
            return plan

        try:
            if self.engage_dom.post_has_user_comment(post_root):
                logger.info("Skipping comment: detected existing user comment in root")
                if urn:
                    self.ctx.commented_urns.add(urn)
                plan.skip_reason = "user_comment_exists"
                return plan
        except WebDriverException:
            pass

        try:
            if self.engage_dom.post_has_similar_comment(post_root, plan.text):
                logger.info("Skipping comment: similar comment text already present in root")
                if urn:
                    self.ctx.commented_urns.add(urn)
                plan.skip_reason = "similar_comment_exists"
                return plan
        except WebDriverException:
            pass

        return plan

    def _determine_comment_text(self, post_root) -> Tuple[Optional[str], Optional[str]]:
        """Produce comment text and perspective for the current post.

        WHY
          Return the best text available: AI generated when a client is set,
          otherwise the static CLI text. A failed AI call falls back to the
          static text instead of aborting the run.

        Args
          post_root: WebElement, the post container to read.

        Returns
          Tuple[Optional[str], Optional[str]], the comment text and the chosen
          perspective, either of which may be None.
        """
        perspective = None
        text = self.ctx.comment_text

        if self.ctx.ai_enabled:
            ai_post_text = self.engage_dom.extract_text_for_ai(
                post_root, self.ctx.post_extractor
            )
            if not ai_post_text:
                logger.info("ENGAGE_AI skip: empty post text for AI generation")
            else:
                summary_text = summarize_post_text(ai_post_text) or ai_post_text
                logger.info("ENGAGE_AI summary: %s", summary_text)
                perspective = choose_ai_perspective(self.ctx.ai_perspectives)
                try:
                    text, tone_used = self.ctx.ai_client.generate_comment(
                        post_text=summary_text,
                        perspective=perspective,
                        max_tokens=self.ctx.ai_max_tokens,
                        temperature=self.ctx.ai_temperature,
                    )
                    perspective = tone_used
                except AiError as err:
                    logger.error(f"AI comment generation failed: {err}")
                    text = self.ctx.comment_text

        if text is not None:
            text = str(text).strip()
            if not text:
                text = None

        return text, perspective

    def _perform_comment(
        self,
        bar,
        plan: CommentPlan,
        post_root,
        key: str,
        urn: Optional[str],
        data_id: Optional[str],
    ) -> bool:
        """Execute a comment action based on the prepared plan.

        WHY
          Submit the planned comment and record it across the run and across
          runs, so the same post is not commented twice.

        Args
          bar: WebElement, the action bar for the post.
          plan: CommentPlan, the text and perspective to submit.
          post_root: WebElement, the post container.
          key: str, the primary dedupe key.
          urn: Optional[str], the post URN.
          data_id: Optional[str], the extra dedupe identifier.

        Returns
          bool, True when the comment was submitted, False otherwise.

        MUTATIONS
          Increments ``ctx.actions_done``, adds to ``ctx.commented`` and
          ``ctx.commented_urns``, sets the last perspective, stores the URN
          timestamp in ``ctx.state``, saves that state to disk, and adds the
          data ID to the processed set.
        """
        success = self.engage_dom.comment_from_bar(
            bar,
            plan.text,
            mention_author=self.ctx.mention_author,
            mention_position=self.ctx.mention_position,
            author_name=plan.author_name,
        )
        if not success:
            return False

        self.ctx.actions_done += 1
        self.ctx.commented.add(key)
        self.ctx.ai_last_perspective = plan.perspective
        if urn:
            self.ctx.commented_urns.add(urn)
            try:
                self.ctx.state.setdefault("commented_urns_ts", {})[urn] = time.time()
                self.engage_dom.save_engage_state(self.ctx.state)
            except (OSError, TypeError):
                pass
        if data_id:
            self.ctx.processed_ids.add(data_id)

        self._log_comment_success(urn)
        self.engage_service.action_pause(self.ctx)
        return True

    def _log_comment_success(self, urn: Optional[str]) -> None:
        """Log metadata after successfully commenting on a post.

        WHY
          Show the operator which post was commented, with what perspective and
          how many actions are done.

        Args
          urn: Optional[str], the URN of the commented post.
        """
        if self.ctx.ai_last_perspective:
            logger.info(
                f"Commented post urn={urn or 'unknown'} "
                f"perspective={self.ctx.ai_last_perspective} "
                f"(actions={self.ctx.actions_done}/{self.ctx.max_actions})"
            )
        else:
            logger.info(
                f"Commented post urn={urn or 'unknown'} "
                f"(actions={self.ctx.actions_done}/{self.ctx.max_actions})"
            )

    def _maybe_like_after_comment(self, bar, post_root, key: str, urn: Optional[str]) -> None:
        """Optionally like a post after leaving a comment.

        WHY
          Mimic human behaviour where a comment is often followed by a like.
          The like only counts toward the action cap in both mode, and any
          failure is swallowed so it cannot undo the comment.

        Args
          bar: WebElement, the action bar for the post.
          post_root: WebElement, the post container.
          key: str, the primary dedupe key.
          urn: Optional[str], the post URN.

        MUTATIONS
          Adds the post to ``ctx.liked``, and in both mode increments
          ``ctx.actions_done``.
        """
        try:
            if self.engage_service.is_liked(self.ctx, urn, key):
                return
            if self.engage_dom.like_from_bar(bar):
                self.engage_service.mark_post_liked(self.ctx, urn, key)
                if self.ctx.mode == "both":
                    self.ctx.actions_done += 1
                    logger.info(
                        f"Liked post after comment urn={urn or 'unknown'} "
                        f"(actions={self.ctx.actions_done}/{self.ctx.max_actions})"
                    )
                else:
                    logger.info("Ensured courtesy like after comment (not counted)")
                self.engage_service.action_pause(self.ctx)
        except WebDriverException:
            pass

    def _attempt_like_only(self, bar, post_root, key: str, urn: Optional[str]) -> bool:
        """Perform a like action when the mode is like-only.

        WHY
          Run a like focused session without comments, while never liking the
          same post twice in one run.

        Args
          bar: WebElement, the action bar for the post.
          post_root: WebElement, the post container.
          key: str, the primary dedupe key.
          urn: Optional[str], the post URN.

        Returns
          bool, True when the like is applied, False when skipped or failed.

        MUTATIONS
          Increments ``ctx.actions_done`` and adds the post to ``ctx.liked``.
        """
        if self.engage_service.is_liked(self.ctx, urn, key):
            return False
        if not self.engage_dom.like_from_bar(bar):
            return False

        self.ctx.actions_done += 1
        self.engage_service.mark_post_liked(self.ctx, urn, key)
        logger.info(
            f"Liked post urn={urn or 'unknown'} "
            f"(actions={self.ctx.actions_done}/{self.ctx.max_actions})"
        )
        self.engage_service.action_pause(self.ctx)
        return True

    def _can_take_action(self) -> bool:
        """Check whether the executor is allowed to perform another action.

        WHY
          Hold a finite run to its action cap, while letting an infinite run
          keep going.

        Returns
          bool, True when infinite or under the cap, False when the cap is met.
        """

        return self.ctx.infinite or self.ctx.actions_done < self.ctx.max_actions
