"""Execution logic coordinating the engage-stream iteration loop.

Why:
    Separate orchestration concerns from DOM helpers to keep responsibilities
    clear and testable.

When:
    Instantiated by :class:`EngageStreamMixin` to run the feed engagement loop.

How:
    Loads persisted state, navigates the feed, iterates posts, and handles liking
    and commenting while respecting limits and AI integration.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple
import time

import config
from .engage_types import EngageContext, CommentPlan
from .engage_utils import choose_ai_perspective, pause_between, summarize_post_text
from .engage_utils import choose_ai_perspective, pause_between, summarize_post_text
from selenium.webdriver.common.by import By
from ui_selectors import EngageSelectors


class EngageExecutor:
    """Drive the engage stream using a :class:`LinkedInInteraction` instance.

    Why:
        Decouple the loop mechanics from the mixin interface while keeping
        state handling and logging cohesive.

    When:
        Created by :class:`EngageStreamMixin` for each engage run.

    How:
        Stores the interaction object and context, prepares state, navigates to
        the feed, iterates posts, and applies likes/comments respecting limits.
    """

    def __init__(self, interaction, context: EngageContext) -> None:
        """Store the interaction facade and runtime context.

        Args:
            interaction (LinkedInInteraction): Active interaction mixin instance.
            context (EngageContext): Configuration and mutable state for the run.
        """
        self.x = interaction
        self.ctx = context

    # Public entry points -------------------------------------------------

    def prepare_state(self) -> None:
        """Load and prune engage-state history before running.

        Why:
            Keeps dedupe caches relevant while discarding expired entries.

        When:
            Called once before navigation begins.

        How:
            Loads persisted state via :meth:`EngageDomMixin._load_engage_state`,
            removes URNs older than the TTL, and updates the context sets.

        Returns:
            None
        """
        state = self.x._load_engage_state()
        timestamps = state.get('commented_urns_ts') or {}
        kept = {}
        now = time.time()
        ttl_days = 7
        for urn, ts in list(timestamps.items()):
            try:
                if now - float(ts) < ttl_days * 86400:
                    kept[urn] = float(ts)
            except Exception:
                continue
        state['commented_urns_ts'] = kept
        self.ctx.state = state
        self.ctx.commented_urns.update(kept.keys())

    def navigate_to_feed(self) -> None:
        """Open the LinkedIn feed and clear overlays before engagement.

        Why:
            Ensures the viewport is ready for scrolling and interactions.

        When:
            Invoked immediately after :meth:`prepare_state`.

        How:
            Loads the feed URL, observes configured load delays, and dismisses
            common overlays.

        Returns:
            None
        """
        try:
            self.x.driver.get(config.LINKEDIN_FEED_URL)
        except Exception:
            pass
        pause_between(config.MIN_PAGE_LOAD_DELAY, config.MAX_PAGE_LOAD_DELAY)
        try:
            self.x.dismiss_overlays()
        except Exception:
            pass

    def run(self) -> bool:
        """Execute the engagement loop until limits or cancellation occur.

        Why:
            Central loop iterating posts, invoking comment/like actions, and
            handling pagination.

        When:
            Called after navigation is complete.

        How:
            Processes posts until hitting action limits, scrolling as needed, and
            responds to keyboard interrupts gracefully.

        Returns:
            bool: ``True`` when the loop exits normally, ``False`` if errors arise.
        """
        while True:
            if not self.ctx.infinite and self.ctx.actions_done >= self.ctx.max_actions:
                break

            posts = self.x._find_visible_posts(limit=12)
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

            if (self.ctx.infinite or self.ctx.actions_done < self.ctx.max_actions) and not made_progress:
                self._handle_no_progress()

        logging.info(f"Engage stream finished (actions={self.ctx.actions_done})")
        return True

    # Internals -----------------------------------------------------------

    def _handle_empty_viewport(self) -> bool:
        """React to a viewport with no detectable posts.

        Why:
            Occurs when scrolled near the end or after UI hiccups; needs
            additional scrolling to continue.

        When:
            Triggered when :meth:`_find_visible_posts` returns an empty list.

        How:
            Logs the situation, performs a scroll, compares keys, and falls back
            to aggressive loading when necessary.

        Returns:
            bool: ``True`` if the executor should stop, ``False`` to continue.
        """
        try:
            logging.info("SCROLL_LOOP no_posts_found -> scroll_feed")
        except Exception:
            pass

        prev_keys = self.x._visible_post_keys(limit=12)
        self.x._scroll_feed(self.ctx.scroll_wait_min, self.ctx.scroll_wait_max)
        now_keys = self.x._visible_post_keys(limit=12)
        if set(now_keys) == set(prev_keys):
            self.x._aggressive_load_more(prev_keys, tries=3, wait_min=self.ctx.scroll_wait_min, wait_max=self.ctx.scroll_wait_max)

        self.ctx.page_scrolls += 1
        if not self.ctx.infinite and self.ctx.page_scrolls > 20:
            logging.info("No more posts found after many scrolls; stopping")
            return True
        return False

    def _handle_no_progress(self) -> None:
        """Respond to a viewport pass that yielded no new actions.

        Why:
            Avoids getting stuck on stale content when posts are already processed.

        When:
            Called after iterating visible posts without performing any actions.

        How:
            Logs context, performs a regular scroll, and escalates to aggressive
            loading if new keys are not detected.

        Returns:
            None
        """
        try:
            logging.info("SCROLL_LOOP no_progress_in_viewport -> scroll_feed")
        except Exception:
            pass
        prev_keys = self.x._visible_post_keys(limit=16)
        self.x._scroll_feed(self.ctx.scroll_wait_min, self.ctx.scroll_wait_max)
        now_keys = self.x._visible_post_keys(limit=16)
        if set(now_keys) == set(prev_keys):
            self.x._aggressive_load_more(prev_keys, tries=3, wait_min=self.ctx.scroll_wait_min, wait_max=self.ctx.scroll_wait_max)

    def _process_post(self, post_root) -> bool:
        """Evaluate a single post for commenting and/or liking.

        Why:
            Central decision-maker determining whether to interact with a post.

        When:
            Called for each visible post in the viewport.

        How:
            Scrolls into view, extracts dedupe keys, skips previously processed
            posts or promoted content, locates the action bar, and performs
            comment/like actions as dictated by the context.

        Args:
            post_root (WebElement): Post container element.

        Returns:
            bool: ``True`` if any action occurred, ``False`` otherwise.
        """
        progress = False
        try:
            self.x._scroll_into_view(post_root)
            self.x._action_pause(self.ctx, 0.3, 0.7)
        except Exception:
            pass

        urn = self.x._extract_post_urn(post_root)
        data_id = self.x._extract_data_id(post_root)
        text_key = self.x._post_text_key(post_root)
        key = self.x._post_dedupe_key(post_root, urn)
        try:
            logging.info(
                f"ENGAGE_KEYS urn={urn or 'none'} data_id={data_id or 'none'} key={key[:8]} "
                f"text_key={text_key[:8] if text_key else 'none'}"
            )
        except Exception:
            pass

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

        if self.ctx.mode in ('comment', 'both') and self._can_take_action():
            plan = self._prepare_comment_plan(post_root, bar, urn)
            if plan.skip_reason:
                return False
            if plan.text and self._perform_comment(bar, plan, post_root, key, urn, data_id):
                progress = True
                self._maybe_like_after_comment(bar, post_root, key, urn)

        if self.ctx.mode == 'like' and self._can_take_action():
            if self._attempt_like_only(bar, post_root, key, urn):
                progress = True

        return progress

    def _should_skip_post(self, post_root, key: str, text_key: Optional[str], data_id: Optional[str]) -> bool:
        """Decide whether to skip a post based on dedupe and filters.

        Why:
            Prevents repeated interactions and avoids promoted content when disallowed.

        When:
            Invoked near the start of :meth:`_process_post`.

        How:
            Checks processed sets, DOM markers, and promotion status, logging
            reasons for skips.

        Args:
            post_root (WebElement): Post element under consideration.
            key (str): Primary dedupe key.
            text_key (str | None): Text-based dedupe key.
            data_id (str | None): Additional dedupe identifier.

        Returns:
            bool: ``True`` when the post should be skipped.
        """
        if key in self.ctx.processed:
            logging.info("ENGAGE_SKIP reason=processed_key")
            return True
        if text_key and text_key in self.ctx.processed_text_keys:
            logging.info("ENGAGE_SKIP reason=processed_text_key")
            return True
        if data_id and data_id in self.ctx.processed_ids:
            logging.info("ENGAGE_SKIP reason=processed_data_id")
            return True

        try:
            marker = self.x.driver.execute_script(
                "return arguments[0].getAttribute('data-li-bot-commented');",
                post_root,
            )
            if str(marker).strip() == '1':
                self.ctx.processed.add(key)
                if text_key:
                    self.ctx.processed_text_keys.add(text_key)
                if data_id:
                    self.ctx.processed_ids.add(data_id)
                logging.info("ENGAGE_SKIP reason=dom_mark_commented")
                return True
        except Exception:
            pass

        if not self.ctx.include_promoted and self.x._is_promoted_post(post_root):
            logging.debug(f"Skipping promoted post (urn={key or 'unknown'})")
            self.ctx.processed.add(key)
            if text_key:
                self.ctx.processed_text_keys.add(text_key)
            logging.info("ENGAGE_SKIP reason=promoted")
            return True

        return False

    def _locate_action_bar(self, post_root):
        """Return the social action bar associated with a post.

        Why:
            Action buttons live inside this container and are needed for likes/comments.

        When:
            Called before performing any action on a post.

        How:
            Searches for known class patterns within the post root.

        Args:
            post_root (WebElement): Post container.

        Returns:
            WebElement | None: Action bar when found, otherwise ``None``.
        """
        try:
            return post_root.find_element(By.XPATH, EngageSelectors.ACTION_BAR)
        except Exception:
            return None

    def _prepare_comment_plan(self, post_root, bar, urn: Optional[str]) -> CommentPlan:
        """Determine whether to comment on a post and how.

        Why:
            Encapsulates decision-making (skip reasons, AI generation) before performing a comment.

        When:
            Called per post when the context mode includes commenting.

        How:
            Validates dedupe conditions, ensures comment text exists (via AI or
            static), collects author info, and returns a :class:`CommentPlan`.

        Args:
            post_root (WebElement): Post container.
            bar (WebElement): Action bar element for the post.
            urn (str | None): Post URN if available.

        Returns:
            CommentPlan: Plan indicating comment text, perspective, and skip reason.
        """
        plan = CommentPlan(text=None, perspective=None, author_name=None, skip_reason=None)

        if self.ctx.mode not in ('comment', 'both'):
            plan.skip_reason = 'comments_disabled'
            return plan

        if self.ctx.mention_author:
            try:
                plan.author_name = self.x._extract_author_name(post_root)
            except Exception:
                plan.author_name = None

        if self.ctx.mode == 'comment':
            try:
                if self.x._is_liked(bar):
                    logging.info("Skipping comment: post already liked (gate, comment-only mode)")
                    plan.skip_reason = 'already_liked'
                    return plan
            except Exception:
                pass

        if urn and urn in self.ctx.commented_urns:
            logging.info("Skipping comment: URN already commented this run")
            plan.skip_reason = 'urn_already_commented'
            return plan

        plan.text, plan.perspective = self._determine_comment_text(post_root)

        if not plan.text:
            logging.info("ENGAGE_SKIP reason=no_comment_text_available")
            plan.skip_reason = 'no_comment_text'
            return plan

        try:
            if self.x._post_has_user_comment(post_root):
                logging.info("Skipping comment: detected existing user comment in root")
                if urn:
                    self.ctx.commented_urns.add(urn)
                plan.skip_reason = 'user_comment_exists'
                return plan
        except Exception:
            pass

        try:
            if self.x._post_has_similar_comment(post_root, plan.text):
                logging.info("Skipping comment: similar comment text already present in root")
                if urn:
                    self.ctx.commented_urns.add(urn)
                plan.skip_reason = 'similar_comment_exists'
                return plan
        except Exception:
            pass

        return plan

    def _determine_comment_text(self, post_root) -> Tuple[Optional[str], Optional[str]]:
        """Produce comment text and perspective for the current post.

        Why:
            Comment content may originate from CLI text or AI generation.

        When:
            Called by :meth:`_prepare_comment_plan` for comment-capable modes.

        How:
            Extracts post text, optionally summarises, chooses a perspective, and
            invokes the AI client if available, falling back to static text.

        Args:
            post_root (WebElement): Post container to analyse.

        Returns:
            tuple[Optional[str], Optional[str]]: Comment text and chosen perspective.
        """
        perspective = None
        text = self.ctx.comment_text

        if self.ctx.ai_enabled:
            ai_post_text = self.x._extract_text_for_ai(post_root, self.ctx.post_extractor)
            if not ai_post_text:
                logging.info("ENGAGE_AI skip: empty post text for AI generation")
            else:
                summary_text = summarize_post_text(ai_post_text) or ai_post_text
                logging.info("ENGAGE_AI summary: %s", summary_text)
                perspective = choose_ai_perspective(self.ctx.ai_perspectives)
                try:
                    text = self.ctx.ai_client.generate_comment(
                        post_text=summary_text,
                        perspective=perspective,
                        max_tokens=self.ctx.ai_max_tokens,
                        temperature=self.ctx.ai_temperature,
                    )
                except Exception as err:
                    logging.error(f"AI comment generation failed: {err}")
                    text = self.ctx.comment_text

        if text is not None:
            text = str(text).strip()
            if not text:
                text = None

        return text, perspective

    def _perform_comment(self, bar, plan: CommentPlan, post_root, key: str, urn: Optional[str], data_id: Optional[str]) -> bool:
        """Execute a comment action based on the prepared plan.

        Why:
            Applies the plan and updates context state when a comment is successful.

        When:
            Called after :meth:`_prepare_comment_plan` returns a non-skipped plan.

        How:
            Uses DOM helpers to submit the comment, updates action counts, marks
            processed sets, and persists state.

        Args:
            bar (WebElement): Action bar element for the post.
            plan (CommentPlan): Comment plan containing text/perspective info.
            post_root (WebElement): Post container.
            key (str): Dedupe key.
            urn (str | None): Post URN.
            data_id (str | None): Additional dedupe identifier.

        Returns:
            bool: ``True`` if the comment was submitted, else ``False``.
        """
        success = self.x._comment_from_bar(
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
                self.ctx.state.setdefault('commented_urns_ts', {})[urn] = self.x.time.time()
                self.x._save_engage_state(self.ctx.state)
            except Exception:
                pass
        if data_id:
            self.ctx.processed_ids.add(data_id)

        self._log_comment_success(urn)
        self.x._action_pause(self.ctx)
        return True

    def _log_comment_success(self, urn: Optional[str]) -> None:
        """Log metadata after successfully commenting on a post.

        Why:
            Provides observability into which posts were commented and with what perspective.

        When:
            Called after :meth:`_perform_comment` succeeds.

        How:
            Emits structured logging including URN, perspective, and action counts.

        Args:
            urn (str | None): URN for the commented post.

        Returns:
            None
        """
        try:
            if self.ctx.ai_last_perspective:
                logging.info(
                    f"Commented post urn={urn or 'unknown'} perspective={self.ctx.ai_last_perspective} "
                    f"(actions={self.ctx.actions_done}/{self.ctx.max_actions})"
                )
            else:
                logging.info(
                    f"Commented post urn={urn or 'unknown'} (actions={self.ctx.actions_done}/{self.ctx.max_actions})"
                )
        except Exception:
            logging.info(
                f"Commented post urn={urn or 'unknown'} (actions={self.ctx.actions_done}/{self.ctx.max_actions})"
            )

    def _maybe_like_after_comment(self, bar, post_root, key: str, urn: Optional[str]) -> None:
        """Optionally like a post after leaving a comment.

        Why:
            Mimics human behaviour where a comment is often accompanied by a like.

        When:
            Called after a comment is posted.

        How:
            Checks whether the post was already liked, attempts a like via
            :meth:`EngageDomMixin._like_from_bar`, updates context state, and logs.

        Args:
            bar (WebElement): Action bar element for the post.
            post_root (WebElement): Post container.
            key (str): Dedupe key.
            urn (str | None): Post URN.

        Returns:
            None
        """
        try:
            if key in self.ctx.liked:
                return
            if self.x._like_from_bar(bar):
                self.ctx.liked.add(key)
                if self.ctx.mode == 'both':
                    self.ctx.actions_done += 1
                    logging.info(
                        f"Liked post after comment urn={urn or 'unknown'} (actions={self.ctx.actions_done}/{self.ctx.max_actions})"
                    )
                else:
                    logging.info("Ensured courtesy like after comment (not counted)")
                try:
                    self.x._mark_post_liked(post_root, bar)
                except Exception:
                    pass
                self.x._action_pause(self.ctx)
        except Exception:
            pass

    def _attempt_like_only(self, bar, post_root, key: str, urn: Optional[str]) -> bool:
        """Perform a like action when the mode is like-only.

        Why:
            Enables like-focused sessions without comments.

        When:
            Called within :meth:`_process_post` for `mode == 'like'`.

        How:
            Skips already liked posts, attempts a like, updates context and logs
            outcomes.

        Args:
            bar (WebElement): Action bar element.
            post_root (WebElement): Post container.
            key (str): Dedupe key.
            urn (str | None): Post URN.

        Returns:
            bool: ``True`` when the like is applied, ``False`` otherwise.
        """
        if key in self.ctx.liked or self.x._is_post_marked_liked(post_root):
            return False
        if not self.x._like_from_bar(bar):
            return False

        self.ctx.actions_done += 1
        self.ctx.liked.add(key)
        logging.info(
            f"Liked post urn={urn or 'unknown'} (actions={self.ctx.actions_done}/{self.ctx.max_actions})"
        )
        try:
            self.x._mark_post_liked(post_root, bar)
        except Exception:
            pass
        self.x._action_pause(self.ctx)
        return True

    def _can_take_action(self) -> bool:
        """Check whether the executor is allowed to perform another action.

        Why:
            Prevents exceeding configured action limits unless running infinitely.

        When:
            Evaluated before attempting any like/comment.

        How:
            Returns ``True`` when running in infinite mode or the action count is
            below the limit.

        Returns:
            bool: Permission status for performing another action.
        """

        return self.ctx.infinite or self.ctx.actions_done < self.ctx.max_actions
