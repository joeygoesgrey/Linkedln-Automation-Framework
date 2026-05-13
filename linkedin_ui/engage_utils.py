"""Utility helpers shared across engage-stream logic.

Why:
    Provide reusable calculations (delays, perspective normalisation, text
    summarisation) used by multiple engage components.

When:
    Imported primarily by :mod:`linkedin_ui.engage` and :mod:`engage_flow`.

How:
    Exposes standalone functions to keep the main modules lean.
"""

from __future__ import annotations

import logging
import random
import time
from typing import List, Optional
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer


def pause_between(min_seconds: float, max_seconds: float) -> None:
    """Sleep for a random interval within the provided bounds.

    Why:
        Simulate human delay between actions, reducing bot detection risk.

    When:
        Used by engage flows where a temporary pause is needed outside of class methods.

    How:
        Chooses a uniform random number between the min/max, clamped to positive values.

    Args:
        min_seconds (float): Lower bound for the sleep interval.
        max_seconds (float): Upper bound for the sleep interval.

    Returns:
        None
    """

    high = max(min_seconds, max_seconds)
    low = min(min_seconds, max_seconds)
    time.sleep(random.uniform(max(0.05, low), max(0.1, high)))


def normalize_perspectives(perspectives: Optional[List[str]]) -> List[str]:
    """Normalise perspective labels to recognised values.

    Why:
        Accepts friendly aliases (`perspective`) and ensures downstream logic receives canonical names.

    When:
        Called when building the engage context.

    How:
        Returns defaults when the list is empty and replaces ``"perspective"`` with ``"insightful"``.

    Args:
        perspectives (list[str] | None): Perspectives supplied by CLI callers.

    Returns:
        list[str]: Normalised perspective names.
    """

    if not perspectives:
        return ["funny", "motivational", "insightful"]
    normalized: List[str] = []
    for item in perspectives:
        normalized.append("insightful" if item == "perspective" else item)
    return normalized or ["funny", "motivational", "insightful"]


def choose_ai_perspective(perspectives: List[str]) -> str:
    """Pick a random perspective token from allowed values.

    Why:
        Introduces variation in AI-generated comments to avoid repetition.

    When:
        Called before requesting AI comment text.

    How:
        Filters the provided list to the allowed set and chooses randomly,
        defaulting to the allowed set when necessary.

    Args:
        perspectives (list[str]): Candidate perspective names.

    Returns:
        str: Perspective string to embed in AI prompts.
    """

    allowed = ["funny", "motivational", "insightful"]
    pool = [p for p in perspectives if p in allowed] or allowed
    return random.choice(pool)


def summarize_post_text(text: str, sentences: int = 3) -> Optional[str]:
    """Condense lengthy post text using Sumy's TextRank summariser.

    Why:
        Keeps AI prompt size manageable while retaining key ideas.

    When:
        Used before generating AI comments when posts exceed heuristics for length.

    How:
        Runs Sumy's TextRank summariser when text is longer than the threshold,
        falling back to whitespace-normalised text on failure.

    Args:
        text (str): Source post content.
        sentences (int): Target number of sentences for the summary.

    Returns:
        str | None: Condensed text or ``None`` when input is empty.
    """

    if not text:
        return None
    if len(text) < 400 or text.count(" ") < 60:
        return text.strip()

    try:
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = TextRankSummarizer()
        summary = [str(sentence) for sentence in summarizer(parser.document, sentences)]
        condensed = " ".join(summary).strip()
        condensed = " ".join(condensed.split())
        return condensed or " ".join(text.split())
    except Exception as err:
        try:
            logging.debug(f"SUMMARIZE fallback (sumy error): {err}")
        except Exception:
            pass
        return " ".join(text.split())
