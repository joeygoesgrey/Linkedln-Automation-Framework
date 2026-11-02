"""Utility helpers shared across engage-stream logic.

WHY
  Keep delay, perspective and text-summary rules in one place, so the engage
  flow and the DOM layer apply the same behaviour.
"""

from __future__ import annotations

import logging
import random
import time
from typing import List, Optional

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.text_rank import TextRankSummarizer

logger = logging.getLogger(__name__)

# Tones the model may write a comment in. Auto is a separate mode, not a tone.
COMMENT_TONES: List[str] = ["motivational", "thoughtful", "reality_check"]
COMMENT_PERSPECTIVES: List[str] = [*COMMENT_TONES, "auto"]
_PERSPECTIVE_ALIASES = {"insightful": "thoughtful"}


def pause_between(min_seconds: float, max_seconds: float) -> None:
    """Sleep for a random interval within the provided bounds.

    WHY
      Simulate a human pause between actions, so the run does not hammer the
      feed at a fixed machine speed.

    Args
      min_seconds: float, one delay bound from the caller.
      max_seconds: float, the other delay bound from the caller.

    MUTATIONS
      Blocks the current thread for the chosen interval.
    """

    high = max(min_seconds, max_seconds)
    low = min(min_seconds, max_seconds)
    time.sleep(random.uniform(max(0.05, low), max(0.1, high)))


def normalize_perspectives(perspectives: Optional[List[str]]) -> List[str]:
    """Normalise perspective labels to recognised values.

    WHY
      Accept the old alias and drop unknown words, so AI comment generation
      always gets a valid choice and an empty or broken input runs in auto.

    Args
      perspectives: Optional[List[str]], the raw labels from the CLI caller.

    Returns
      List[str], the canonical labels, or ["auto"] when the input is empty or
      holds no recognised value.
    """

    if not perspectives:
        return ["auto"]
    normalized: List[str] = []
    for item in perspectives:
        value = item.strip().lower()
        value = _PERSPECTIVE_ALIASES.get(value, value)
        if value in COMMENT_PERSPECTIVES and value not in normalized:
            normalized.append(value)
    return normalized or ["auto"]


def choose_ai_perspective(perspectives: List[str]) -> str:
    """Pick the tone to use for one comment.

    WHY
      Auto must reach the model unchanged, while an explicit list still varies
      the tone between comments, so the replies do not all sound the same.

    Args
      perspectives: List[str], the candidate labels held in the context.

    Returns
      str, "auto" when the list asks for it, otherwise a random allowed tone.
    """

    if "auto" in perspectives:
        return "auto"
    pool = [p for p in perspectives if p in COMMENT_TONES] or COMMENT_TONES
    return random.choice(pool)


def reaction_already_set(button) -> bool:
    """Report whether a reaction control already holds a chosen reaction.

    WHY
      Clicking the reaction control on a post that is already liked removes the
      like, so the caller must know the current state before clicking. The new
      feed carries the state in the aria-label and no longer sets aria-pressed.

    Args
      button: WebElement, the reaction control or the element that holds it.

    Returns
      bool, True when the button is pressed or its label reports a reaction.
    """
    try:
        pressed = (button.get_attribute("aria-pressed") or "").lower() == "true"
    except WebDriverException:
        pressed = False
    if pressed:
        return True

    try:
        labels = [button.get_attribute("aria-label") or ""]
        for node in button.find_elements(By.XPATH, ".//*[@aria-label]"):
            labels.append(node.get_attribute("aria-label") or "")
    except WebDriverException:
        return False

    for label in labels:
        lowered = label.lower()
        if "reaction button state" in lowered:
            return "no reaction" not in lowered
    return False


def summarize_post_text(text: str, sentences: int = 3) -> Optional[str]:
    """Condense lengthy post text using Sumy's TextRank summariser.

    WHY
      Keep the AI prompt small while keeping the main ideas, and still return
      usable text when the summariser fails, so a bad parse does not block the
      comment.

    Args
      text: str, the post content read from the DOM.
      sentences: int, the target sentence count for the summary.

    Returns
      Optional[str], the condensed text, the plain text for short input, or
      None when the input is empty.
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
    except (ValueError, LookupError) as err:
        logger.debug("Sumy summarizer failed, using plain text: %s", err)
        return " ".join(text.split())
