"""Typed containers for engage-stream configuration and runtime state.

WHY
  Pass settings and run outcomes between the engage services in one typed
  object, so no caller has to guess the shape or the defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class EngageContext:
    """Hold configuration and mutable state for one engage-stream session.

    WHY
      Consolidate CLI inputs, runtime counters and dedupe caches into one
      object, so the loop reads and writes a single source of truth.

    MUTATIONS
      The executor updates the counters, the processed/liked/commented sets and
      the persisted state dict while the run is in progress.
    """

    mode: str
    comment_text: Optional[str]
    max_actions: int
    include_promoted: bool
    delay_min: float
    delay_max: float
    mention_author: bool
    mention_position: str
    infinite: bool
    scroll_wait_min: float
    scroll_wait_max: float
    ai_client: Any = None
    ai_perspectives: List[str] = field(default_factory=list)
    ai_temperature: float = 0.7
    ai_max_tokens: int = 180
    post_extractor: Any = None
    processed: Set[str] = field(default_factory=set)
    processed_text_keys: Set[str] = field(default_factory=set)
    processed_ids: Set[str] = field(default_factory=set)
    commented: Set[str] = field(default_factory=set)
    commented_urns: Set[str] = field(default_factory=set)
    liked: Set[str] = field(default_factory=set)
    state: Dict[str, Any] = field(default_factory=dict)
    actions_done: int = 0
    page_scrolls: int = 0
    ai_last_perspective: Optional[str] = None

    @property
    def ai_enabled(self) -> bool:
        """Tell whether AI-assisted commenting is configured for the session.

        WHY
          Let callers skip the AI path before any text is needed, instead of
          failing halfway through a post when no client was supplied.

        Returns
          bool, True when an AI client was supplied to the context.
        """
        return self.ai_client is not None


@dataclass
class CommentPlan:
    """Describe whether and how to comment on a specific post.

    WHY
      Keep the comment decision separate from the DOM action, so the choice can
      be checked and skipped before any text is typed into the page.
    """

    text: Optional[str]
    perspective: Optional[str]
    author_name: Optional[str]
    skip_reason: Optional[str] = None
