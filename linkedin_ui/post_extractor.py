"""Utilities for extracting structured data from LinkedIn feed posts.

Why:
    Summaries and AI comments require clean, expanded post text.

When:
    Instantiated by :class:`LinkedInBot` for engage stream and other analyses.

How:
    Expands truncated sections and gathers visible text using Selenium queries.
"""

from __future__ import annotations

import logging
from typing import Iterable

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config
from ui_selectors import PostExtractorSelectors


class PostExtractor:
    """Best-effort helpers for reading visible post text and metadata.

    Why:
        Keep text extraction logic in one place to simplify reuse and testing.

    When:
        Used before AI summarisation and comment generation.

    How:
        Uses Selenium waits and DOM traversals to expand "see more" sections and
        gather text snippets.
    """

    def __init__(self, driver) -> None:
        """Store the Selenium driver used for post extraction.

        Args:
            driver (selenium.webdriver.Remote): Active WebDriver instance.
        """
        self.driver = driver

    def extract_text(self, root) -> str:
        """Return the visible text content for a post root element.

        Why:
            Engage AI and logging require the full textual content of a post.

        When:
            Called whenever text context is needed, such as before summarising.

        How:
            Expands "see more" sections, then gathers and trims text snippets.

        Args:
            root (WebElement): Post container element.

        Returns:
            str: Combined post text with surrounding whitespace trimmed.
        """
        if root is None:
            return ""
        try:
            self._expand_truncated_sections(root)
        except Exception:
            pass
        try:
            text = self._gather_text(root)
        except Exception:
            logging.debug("PostExtractor fallback to raw text", exc_info=True)
            text = (root.text or "")
        return text.strip()

    # Internal helpers -----------------------------------------------------

    def _expand_truncated_sections(self, root) -> None:
        """Expand truncated content by clicking "See more" buttons.

        Why:
            Ensures the extractor captures the complete post text.

        When:
            Invoked as part of :meth:`extract_text`.

        How:
            Searches for known expansion buttons and clicks them until no longer clickable.

        Args:
            root (WebElement): Post container element.

        Returns:
            None
        """
        selectors = PostExtractorSelectors.SEE_MORE_BUTTONS
        for xp in selectors:
            try:
                button = root.find_element(By.XPATH, xp)
                if not button or not button.is_displayed():
                    continue
                try:
                    self.driver.execute_script("arguments[0].click();", button)
                except Exception:
                    button.click()
                WebDriverWait(self.driver, config.SHORT_TIMEOUT).until_not(
                    EC.element_to_be_clickable((By.XPATH, xp))
                )
            except Exception:
                continue

    def _gather_text(self, root) -> str:
        """Collect visible text snippets from a post into a single string.

        Why:
            Breaks down DOM traversal to a reusable helper for extraction.

        When:
            Called after expanding truncated sections.

        How:
            Iterates through known selectors for textual nodes, aggregates unique
            snippets, and falls back to raw text when necessary.

        Args:
            root (WebElement): Post container element.

        Returns:
            str: Combined text truncated to ~1200 characters.
        """
        text_parts: list[str] = []
        seen: set[str] = set()
        selectors: Iterable[str] = PostExtractorSelectors.CONTENT_NODES
        for xp in selectors:
            nodes = root.find_elements(By.XPATH, xp)
            for node in nodes:
                try:
                    if not node.is_displayed():
                        continue
                    snippet = (node.text or "").strip()
                    if not snippet or snippet in seen:
                        continue
                    seen.add(snippet)
                    text_parts.append(snippet)
                except Exception:
                    continue
            if text_parts:
                break
        if not text_parts:
            return (root.text or "").strip()[:1200]
        combined = "\n".join(text_parts)
        return combined[:1200]
