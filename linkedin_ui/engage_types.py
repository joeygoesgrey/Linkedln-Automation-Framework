"""Dataclasses representing engage-stream configuration and runtime state.

Why:
    Provide typed containers for passing configuration and outcomes between
    mixins and executors.

When:
    Instantiated prior to and during engage-stream execution.

How:
    Leverage the Python dataclass decorator to define lightweight, mutable
    structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class EngageContext:
    """Hold configuration and mutable state for an engage-stream session.

    Why:
        Consolidate CLI inputs, runtime counters, and caches into one object.

    When:
        Created prior to executing the engage loop and mutated during runtime.

    How:
        Stores both configuration values (mode, delays) and sets/dicts tracking
        processed posts, liked/commented URNs, and persisted state.
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
        """Whether AI-assisted commenting is configured for the session."""
        return self.ai_client is not None


@dataclass
class CommentPlan:
    """Describe whether and how to comment on a specific post.

    Why:
        Separates decision logic from execution, making it easier to test and
        inspect comment choices.

    When:
        Created per post during :meth:`EngageExecutor._prepare_comment_plan`.

    How:
        Holds the final comment text, chosen perspective, author name, and skip
        reason (if any).
    """

    text: Optional[str]
    perspective: Optional[str]
    author_name: Optional[str]
    skip_reason: Optional[str] = None
