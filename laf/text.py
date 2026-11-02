"""Lightweight helpers for normalising text prior to AI calls.

WHY
  Centralise whitespace and truncation logic so AI prompts stay lean and the
  same cleaning rule is not copied across modules.
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

    WHY
      Reduce noisy whitespace and long bodies so prompts stay concise and
      inside token limits.

    Args
      text: str, the source text from the caller.
      summarize_ratio: Optional[float], the fraction of the text to keep, from
        the caller.
      max_chars: Optional[int], the hard character cap, from the caller.

    Returns
      str, the cleaned and optionally cut text, ready for a prompt.
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
