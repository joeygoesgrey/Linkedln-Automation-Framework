"""
Engage stream: continuously like/comment posts in the home feed.

Why:
    Provide an MVP loop to engage with posts while skipping Promoted content
    and avoiding duplicate actions in a single run.

When:
    Invoked via CLI flags for like|comment|both. Stops after N actions
    (default 12) or on Ctrl+C.

How:
    - Scans visible posts, skipping those marked Promoted.
    - For each post, optionally Like and/or Comment with human-like delays.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Optional, List, Any

import config
from .engage_dom import EngageDomMixin
from .engage_flow import EngageExecutor
from .engage_types import EngageContext
from .engage_utils import normalize_perspectives


class EngageStreamMixin(EngageDomMixin):
    """Coordinate the engage-stream workflow across DOM and flow helpers.

    Why:
        Encapsulate parameter validation, context building, and executor wiring
        so callers only supply CLI-style arguments.

    When:
        Mixed into :class:`LinkedInInteraction` and invoked by engage workflow
        entry points.

    How:
        Validates inputs, builds an :class:`EngageContext`, instantiates
        :class:`EngageExecutor`, and delegates execution.
    """

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

        Why:
            Automates lightweight engagement to boost visibility without manual
            scrolling.

        When:
            Called by CLI flows when `--engage-stream` is provided.

        How:
            Logs context headers, validates arguments, builds an
            :class:`EngageContext`, and executes via :class:`EngageExecutor`.

        Args:
            mode (str): Engagement mode (`like`, `comment`, or `both`).
            comment_text (str | None): Static comment text when AI is disabled.
            max_actions (int): Maximum number of actions to perform.
            include_promoted (bool): Whether to include promoted posts.
            delay_min (float | None): Minimum delay between actions.
            delay_max (float | None): Maximum delay between actions.
            mention_author (bool): Whether to mention the author in comments.
            mention_position (str): Placement of the author mention token.
            infinite (bool): Whether to ignore ``max_actions``.
            scroll_wait_min (float | None): Minimum scroll wait.
            scroll_wait_max (float | None): Maximum scroll wait.
            ai_client: Optional AI client for generating comments.
            ai_perspectives (list[str] | None): Preferred comment perspectives.
            ai_temperature (float): Temperature for AI comments.
            ai_max_tokens (int): Token limit for AI comments.
            post_extractor: Optional post text extractor helper.

        Returns:
            bool: ``True`` on success, ``False`` when validation or execution fails.
        """
        normalized_mode = (mode or "").strip().lower()
        self._log_engage_header(normalized_mode, infinite)

        # Pydantic validation (Standard 3)
        from models import EngageModel
        try:
            validated = EngageModel(
                mode=normalized_mode,
                max_actions=max_actions
            )
        except Exception as e:
            logging.error(f"Validation failed for engage_stream: {e}")
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

        executor = EngageExecutor(self, context)
        executor.prepare_state()
        executor.navigate_to_feed()

        try:
            return executor.run()
        except KeyboardInterrupt:
            logging.info(f"Engage stream cancelled by user (actions={context.actions_done})")
            return True
        except Exception:
            logging.error("Engage stream failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Support methods

    def _log_engage_header(self, mode: str, infinite: bool) -> None:
        """Emit run metadata for logging and debugging.

        Why:
            Provide clear logs for operators monitoring engage behaviour.

        When:
            Called at the start of :meth:`engage_stream`.

        How:
            Logs hardened build info and infinite scroll status.

        Args:
            mode (str): Engagement mode.
            infinite (bool): Whether infinite scrolling is enabled.

        Returns:
            None
        """

        try:
            logging.info("ENGAGE_HARDENED v2025.09-1 active | order=comment-then-like | ttl=7d")
        except Exception:
            pass
        if infinite:
            try:
                logging.info("INF_SCROLL engage: running until Ctrl+C (ignoring --max-actions)")
            except Exception:
                pass

    def _validate_engage_arguments(self, mode: str, comment_text: Optional[str], ai_client) -> bool:
        """Check engage-stream arguments for completeness and compatibility.

        Why:
            Prevents runtime errors by surfacing misconfigurations early.

        When:
            Immediately after logging headers within :meth:`engage_stream`.

        How:
            Validates the mode, ensures comment text is provided when required,
            and logs when AI is enabled.

        Args:
            mode (str): Engagement mode.
            comment_text (str | None): Static fallback comment text.
            ai_client: Optional AI client to generate comments.

        Returns:
            bool: ``True`` when arguments pass validation, ``False`` otherwise.
        """

        if mode not in {"like", "comment", "both"}:
            logging.error("engage_stream mode must be one of: like | comment | both")
            return False

        needs_comment = "comment" in mode
        has_comment = bool(comment_text and str(comment_text).strip())
        if needs_comment and not (has_comment or ai_client):
            logging.error("--stream-comment text is required when mode includes comments")
            return False

        if ai_client is not None:
            try:
                logging.info("ENGAGE_AI comments enabled")
            except Exception:
                pass
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

        Why:
            Normalises inputs and applies defaults before passing state to the
            executor.

        When:
            Called inside :meth:`engage_stream` after validation.

        How:
            Applies defaults, coerces optional values, and returns a populated
            dataclass instance.

        Args:
            mode (str): Engagement mode.
            comment_text (str | None): Static comment text.
            max_actions (int): Maximum action count.
            include_promoted (bool): Whether to include promoted posts.
            delay_min (float | None): Minimum delay override.
            delay_max (float | None): Maximum delay override.
            mention_author (bool): Whether to mention the author.
            mention_position (str): Author mention placement.
            infinite (bool): Run indefinitely flag.
            scroll_wait_min (float | None): Minimum scroll wait.
            scroll_wait_max (float | None): Maximum scroll wait.
            ai_client: AI client for comment generation.
            ai_perspectives (list[str] | None): Comment perspectives.
            ai_temperature (float): Comment temperature.
            ai_max_tokens (int): Comment token limit.
            post_extractor: Helper for extracting post text.

        Returns:
            EngageContext: Prepared context for :class:`EngageExecutor`.
        """

        force_prepend = bool(ai_client)

        return EngageContext(
            mode=mode,
            comment_text=str(comment_text).strip() if comment_text else None,
            max_actions=max_actions,
            include_promoted=include_promoted,
            delay_min=delay_min if delay_min is not None else config.MIN_ACTION_DELAY,
            delay_max=delay_max if delay_max is not None else config.MAX_ACTION_DELAY,
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

    def _action_pause(
        self,
        context: EngageContext,
        min_override: Optional[float] = None,
        max_override: Optional[float] = None,
    ) -> None:
        """Sleep for a random interval respecting the context's delay bounds.

        Why:
            Keeps engagement pacing human-like and adjustable via CLI flags.

        When:
            Called between like/comment actions by :class:`EngageExecutor`.

        How:
            Resolves overrides or defaults from context, clamps values, and
            sleeps for a uniform random duration.

        Args:
            context (EngageContext): Current engagement context.
            min_override (float | None): Optional minimum override.
            max_override (float | None): Optional maximum override.

        Returns:
            None
        """

        min_seconds = min_override if min_override is not None else context.delay_min
        max_seconds = max_override if max_override is not None else context.delay_max
        high = max(min_seconds, max_seconds)
        low = min(min_seconds, max_seconds)
        time.sleep(random.uniform(max(0.05, low), max(0.1, high)))
