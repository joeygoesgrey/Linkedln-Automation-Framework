"""Read clean, expanded text out of LinkedIn feed posts.

WHY
  Summaries and AI comments need the full post text, not the truncated version
  the feed first shows.
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from laf.config import CONFIG, Config
from laf.selectors.feed import PostExtractorSelectors

logger = logging.getLogger(__name__)

class PostExtractor:
    """Read the visible text of a feed post, expanding it first.

    WHY
      Give summarisation and comment generation one clean block of post text
      from any of the DOM shapes LinkedIn serves.
    """

    def __init__(self, driver, config: Optional[Config] = None) -> None:
        """
        WHY
          Store the Selenium driver and settings used for post extraction so
          the extractor can read clean text without the caller wiring settings.

        Args
          driver: the active WebDriver instance.
          config: Config | None, settings to use; defaults to the module CONFIG.

        MUTATIONS
          Stores the driver and settings on the instance.
        """
        self.driver = driver
        self.config = config or CONFIG

    def extract_text(self, root) -> str:
        """Return the full visible text of one post.

        WHY
          Give the AI and the logs the whole post instead of the clipped feed
          preview.

        Args
          root: WebElement, the post container found by the caller.

        Returns
          str, the trimmed post text, or "" when root is None.
        """
        if root is None:
            return ""
        try:
            self._expand_truncated_sections(root)
        except WebDriverException:
            pass
        try:
            text = self._gather_text(root)
        except WebDriverException:
            logger.debug("PostExtractor fallback to raw text", exc_info=True)
            text = root.text or ""
        return text.strip()

    # Internal helpers -----------------------------------------------------

    def _expand_truncated_sections(self, root) -> None:
        """Open a post's clipped section before its text is read.

        WHY
          Without the expanded post, the extractor returns the shortened feed
          preview and misses most of the content.

        Args
          root: WebElement, the post container to expand.
        """
        selectors = PostExtractorSelectors.SEE_MORE_BUTTONS
        for xp in selectors:
            try:
                button = root.find_element(By.XPATH, xp)
                if not button or not button.is_displayed():
                    continue
                try:
                    self.driver.execute_script("arguments[0].click();", button)
                except WebDriverException:
                    button.click()
                WebDriverWait(self.driver, self.config.short_timeout).until_not(
                    EC.element_to_be_clickable((By.XPATH, xp))
                )
            except WebDriverException:
                continue

    def _gather_text(self, root) -> str:
        """Join the unique visible text nodes of a post into one string.

        WHY
          Produces a readable post body from the several DOM nodes LinkedIn
          uses, and falls back to raw text when none match.

        Args
          root: WebElement, the expanded post container.

        Returns
          str, the joined snippets cut to 1200 characters, or the trimmed raw
          text when no node matched.
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
                except WebDriverException:
                    continue
            if text_parts:
                break
        if not text_parts:
            return (root.text or "").strip()[:1200]
        combined = "\n".join(text_parts)
        return combined[:1200]
