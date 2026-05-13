"""Lightweight helpers for normalising text prior to AI calls.

Why:
    Centralise whitespace and truncation logic to keep AI prompts lean while
    avoiding repeated snippets across modules.

When:
    Imported anywhere the project needs to pre-process text before sending it
    to an LLM.

How:
    Exposes small utilities such as :func:`preprocess_for_ai` that perform
    trimming, summarisation by ratio, and character limits.
"""

from __future__ import annotations

import re
from typing import Optional


def preprocess_for_ai(
    text: str,
    summarize_ratio: Optional[float] = None,
    max_chars: Optional[int] = None,
) -> str:
    """Normalise whitespace and optionally truncate strings for AI consumption.

    Why:
        Reducing noisy whitespace and long bodies keeps prompts concise and
        within token limits.

    When:
        Applied prior to OpenAI calls when raw input may contain excess
        spacing or exceed configured limits.

    How:
        Coerces input to ``str``, collapses whitespace, trims by an optional
        ratio, and enforces a maximum character count.

    Args:
        text (str): Source text to clean.
        summarize_ratio (float | None): Optional fraction of the text to retain.
        max_chars (int | None): Hard character cap after cleaning.

    Returns:
        str: Normalised text ready for prompt use.
    """
    if not isinstance(text, str):
        text = str(text or "")

    cleaned = re.sub(r"\s+", " ", text).strip()

    if summarize_ratio is not None and 0 < summarize_ratio < 1:
        cutoff = max(1, int(len(cleaned) * summarize_ratio))
        cleaned = cleaned[:cutoff]

    if max_chars is not None and max_chars > 0:
        cleaned = cleaned[:max_chars]

    return cleaned
