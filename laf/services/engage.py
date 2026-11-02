"""
Engage stream: continuously like and comment on posts in the home feed.

WHY
  Engage with feed posts while skipping Promoted content and avoiding a second
  action on the same post in one run. The loop stops after N actions or on
  Ctrl+C.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, List, Optional, cast

from pydantic import ValidationError
from selenium.common.exceptions import WebDriverException

from laf.config import Config
from laf.models import EngageModel

from ..ui import UiActions
from .engage_dom import EngageDomService
from .engage_flow import EngageExecutor
from .engage_types import EngageContext
from .engage_utils import normalize_perspectives
from .mentions import MentionService
from .overlays import OverlayService

logger = logging.getLogger(__name__)

class EngageService:
    """Coordinate the engage-stream workflow across DOM and flow helpers.

    WHY
      Give the CLI one entry point that checks the arguments, builds the run
      context and hands the loop to the executor.
    """

    def __init__(
        self,
        ui: UiActions,
        config: Config,
        engage_dom: EngageDomService,
        overlays: OverlayService,
        mentions: MentionService,
    ) -> None:
        """
        WHY
          Give the engage stream the driver, settings, DOM readers and mention
          tools it needs to run one session. The AI client and the post
          extractor arrive per call, because they belong to one run, not to the
          long lived service.

        Args
          ui: UiActions, the shared Selenium action helper.
          config: Config, the frozen runtime settings.
          engage_dom: EngageDomService, used to read and act on feed posts.
          overlays: OverlayService, used to clear dialogs over the feed.
          mentions: MentionService, used when comments carry author mentions.
        """
        self.ui = ui
        self.config = config
        self.engage_dom = engage_dom
        self.overlays = overlays
        self.mentions = mentions

    def engage_stream(
        self,
        mode: str,
        comment_text: Optional[str] = None,
        max_actions: int = 12,
        include_promoted: bool = False,
        delay_min: Optional[float] = None,
        delay_max: Optional[float] = None,
        mention_author: bool = False,
        mention_position: str = "append",
        infinite: bool = False,
        scroll_wait_min: Optional[float] = None,
        scroll_wait_max: Optional[float] = None,
        ai_client=None,
        ai_perspectives: Optional[List[str]] = None,
        ai_temperature: float = 0.7,
        ai_max_tokens: int = 180,
        post_extractor=None,
    ) -> bool:
        """Run the engage stream loop with optional AI-powered commenting.

        WHY
          Automate lightweight engagement without manual scrolling, and turn
          any validation or runtime failure into a False result the CLI can
          report instead of a crash. Ctrl+C counts as a clean stop.

        Args
          mode: str, the engagement mode from the CLI flags.
          comment_text: Optional[str], the static comment text when AI is off.
          max_actions: int, the action cap for a finite run.
          include_promoted: bool, whether promoted posts may be engaged.
          delay_min: Optional[float], the minimum pause between actions.
          delay_max: Optional[float], the maximum pause between actions.
          mention_author: bool, whether comments mention the post author.
          mention_position: str, where the author mention is placed.
          infinite: bool, whether to ignore max_actions.
          scroll_wait_min: Optional[float], the minimum wait after a scroll.
          scroll_wait_max: Optional[float], the maximum wait after a scroll.
          ai_client: Any, the client used to generate comments, or None.
          ai_perspectives: Optional[List[str]], the comment styles to choose from.
          ai_temperature: float, the sampling temperature for AI comments.
          ai_max_tokens: int, the token limit for AI comments.
          post_extractor: Any, the optional helper that reads post text.

        Returns
          bool, True when the run finishes or the user cancels, False when
          validation or execution fails.
        """
        normalized_mode = (mode or "").strip().lower()
        self._log_engage_header(normalized_mode, infinite)

        # Pydantic validation (Standard 3)
        try:
            validated = EngageModel(
                mode=cast(Any, normalized_mode), max_actions=max_actions
            )
        except ValidationError as e:
            logger.error(f"Validation failed for engage_stream: {e}")
            return False

        if not self._validate_engage_arguments(validated.mode, comment_text, ai_client):
            return False

        context = self._build_engage_context(
            mode=normalized_mode,
            comment_text=comment_text,
            max_actions=max_actions,
            include_promoted=include_promoted,
            delay_min=delay_min,
            delay_max=delay_max,
            mention_author=mention_author,
            mention_position=mention_position,
            infinite=infinite,
            scroll_wait_min=scroll_wait_min,
            scroll_wait_max=scroll_wait_max,
            ai_client=ai_client,
            ai_perspectives=ai_perspectives,
            ai_temperature=ai_temperature,
            ai_max_tokens=ai_max_tokens,
            post_extractor=post_extractor,
        )

        executor = EngageExecutor(
            self.ui, self.engage_dom, self.overlays, self, self.config, context
        )
        executor.prepare_state()
        executor.navigate_to_feed()

        try:
            return executor.run()
        except KeyboardInterrupt:
            logger.info(f"Engage stream cancelled by user (actions={context.actions_done})")
            return True
        except WebDriverException:
            logger.error("Engage stream failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Support methods

    def _log_engage_header(self, mode: str, infinite: bool) -> None:
        """Emit run metadata for logging and debugging.

        WHY
          Give the operator a clear marker of the build and the scroll mode in
          the log.

        Args
          mode: str, the engagement mode, accepted but not read by the body.
          infinite: bool, whether infinite scrolling is enabled.
        """

        logger.info("ENGAGE_HARDENED v2025.09-1 active | order=comment-then-like | ttl=7d")
        if infinite:
            logger.info("INF_SCROLL engage: running until Ctrl+C (ignoring --max-actions)")

    def _validate_engage_arguments(self, mode: str, comment_text: Optional[str], ai_client) -> bool:
        """Check engage-stream arguments for completeness and compatibility.

        WHY
          Surface a bad mode or a comment run with no text before any browser
          action starts, so the user sees the error instead of a late failure.

        Args
          mode: str, the normalised engagement mode from the CLI.
          comment_text: Optional[str], the static comment text, if any.
          ai_client: Any, the comment generator, if one was supplied.

        Returns
          bool, True when the arguments can run, False when a check fails.
        """

        if mode not in {"like", "comment", "both"}:
            logger.error("engage_stream mode must be one of: like | comment | both")
            return False

        needs_comment = "comment" in mode
        has_comment = bool(comment_text and str(comment_text).strip())
        if needs_comment and not (has_comment or ai_client):
            logger.error("--stream-comment text is required when mode includes comments")
            return False

        if ai_client is not None:
            logger.info("ENGAGE_AI comments enabled")
        return True

    def _build_engage_context(
        self,
        *,
        mode: str,
        comment_text: Optional[str],
        max_actions: int,
        include_promoted: bool,
        delay_min: Optional[float],
        delay_max: Optional[float],
        mention_author: bool,
        mention_position: str,
        infinite: bool,
        scroll_wait_min: Optional[float],
        scroll_wait_max: Optional[float],
        ai_client,
        ai_perspectives: Optional[List[str]],
        ai_temperature: float,
        ai_max_tokens: int,
        post_extractor,
    ) -> EngageContext:
        """Assemble an :class:`EngageContext` from CLI-style arguments.

        WHY
          Apply the config defaults and the alias normalisation once, so the
          executor only sees final values. An AI client forces an author
          mention at the start of the comment.

        Args
          mode: str, the engagement mode.
          comment_text: Optional[str], the static comment text.
          max_actions: int, the action cap for a finite run.
          include_promoted: bool, whether promoted posts may be engaged.
          delay_min: Optional[float], the delay override, or None for config.
          delay_max: Optional[float], the delay override, or None for config.
          mention_author: bool, whether comments mention the post author.
          mention_position: str, where the author mention is placed.
          infinite: bool, whether to ignore max_actions.
          scroll_wait_min: Optional[float], the scroll wait override.
          scroll_wait_max: Optional[float], the scroll wait override.
          ai_client: Any, the comment generator, or None.
          ai_perspectives: Optional[List[str]], the requested comment styles.
          ai_temperature: float, the sampling temperature for AI comments.
          ai_max_tokens: int, the token limit for AI comments.
          post_extractor: Any, the optional helper that reads post text.

        Returns
          EngageContext, the populated context for the executor.
        """

        force_prepend = bool(ai_client)

        return EngageContext(
            mode=mode,
            comment_text=str(comment_text).strip() if comment_text else None,
            max_actions=max_actions,
            include_promoted=include_promoted,
            delay_min=delay_min if delay_min is not None else self.config.min_action_delay,
            delay_max=delay_max if delay_max is not None else self.config.max_action_delay,
            mention_author=mention_author or force_prepend,
            mention_position="prepend" if force_prepend else (mention_position or "append"),
            infinite=infinite,
            scroll_wait_min=scroll_wait_min if scroll_wait_min is not None else 1.5,
            scroll_wait_max=scroll_wait_max if scroll_wait_max is not None else 3.0,
            ai_client=ai_client,
            ai_perspectives=normalize_perspectives(ai_perspectives),
            ai_temperature=ai_temperature,
            ai_max_tokens=ai_max_tokens,
            post_extractor=post_extractor,
        )

    def action_pause(
        self,
        context: EngageContext,
        min_override: Optional[float] = None,
        max_override: Optional[float] = None,
    ) -> None:
        """Sleep for a random interval respecting the context delay bounds.

        WHY
          Keep engagement pacing human-like and adjustable per action, using the
          CLI values unless a caller passes a tighter override.

        Args
          context: EngageContext, the running state that holds the delays.
          min_override: Optional[float], a minimum delay for this pause.
          max_override: Optional[float], a maximum delay for this pause.

        MUTATIONS
          Blocks the current thread for the chosen interval.
        """

        min_seconds = min_override if min_override is not None else context.delay_min
        max_seconds = max_override if max_override is not None else context.delay_max
        high = max(min_seconds, max_seconds)
        low = min(min_seconds, max_seconds)
        time.sleep(random.uniform(max(0.05, low), max(0.1, high)))

    def is_liked(self, context: EngageContext, urn: Optional[str], key: Optional[str]) -> bool:
        """Tell whether a post was already liked in this session.

        WHY
          Guard comment-only runs so a post that was liked is not commented on
          again, using ``context.liked`` as the single source of truth.

        Args
          context: EngageContext, the running state that holds liked keys.
          urn: Optional[str], the post URN when one was found.
          key: Optional[str], the dedupe key for the post.

        Returns
          bool, True when the URN or the key is already in ``context.liked``.
        """
        if urn and urn in context.liked:
            return True
        return bool(key and key in context.liked)

    def mark_post_liked(
        self,
        context: EngageContext,
        urn: Optional[str],
        key: Optional[str],
    ) -> None:
        """Record a liked post in the running context.

        WHY
          ``context.liked`` is the one truth that stops a second like on the
          same post during one run, so no mark is written into the page.

        Args
          context: EngageContext, the running state that holds liked keys.
          urn: Optional[str], the post URN when one was found.
          key: Optional[str], the dedupe key for the post.

        MUTATIONS
            Adds the key and the URN to ``context.liked``.
        """
        if key:
            context.liked.add(key)
        if urn:
            context.liked.add(urn)
