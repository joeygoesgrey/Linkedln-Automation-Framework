"""Verify that a submitted post reached the LinkedIn feed.

WHY
  Catch a failed submission right after it happens instead of assuming the
  post went out.
"""

import logging
import time

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from laf.selectors.verify import VerifySelectors

from ..ui import UiActions

logger = logging.getLogger(__name__)

class VerifyService:
    """Judge from the LinkedIn UI whether a submitted post reached the feed.

    WHY
      Give the composer a yes or no it can log and act on, rather than a
      silent assumption that every post worked.
    """

    def __init__(self, ui: UiActions) -> None:
        """
        WHY
          Give the verification code the shared driver and the timeout setting
          without asking every caller to pass them on each check.

        Args
          ui: UiActions, the shared Selenium action helper.

        MUTATIONS
          Stores the driver helper and its config on the instance.
        """
        self.ui = ui
        self.config = ui.config

    def verify_post_success(self, post_text):
        """Decide from the page state whether the post actually went out.

        WHY
          Treat a composer that is still open, or that shows an error, as a
          failed post instead of a success.

        Args
          post_text: str, the text that was submitted, used to look for the post
            snippet in the feed.

        Returns
          bool, True when the composer is closed and the feed or share box is
          back, False when an error modal remains or no success sign appears.
        """

        logger.info("Verifying post success...")
        time.sleep(3)
        success_indicators = VerifySelectors.SUCCESS_INDICATORS
        for selector in success_indicators:
            try:
                WebDriverWait(self.ui.driver, self.config.short_timeout).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                logger.info(f"Found success indicator: {selector}")
                break
            except TimeoutException:
                continue
        try:
            post_modal = self.ui.driver.find_element(By.XPATH, VerifySelectors.POST_MODAL)
            logger.info("Post modal still exists, post might not be complete")
            try:
                error_message = post_modal.find_element(By.XPATH, VerifySelectors.POST_MODAL_ERROR)
                error_text = error_message.text.strip()
                logger.error(f"Error message found in post modal: {error_text}")
                return False
            except WebDriverException:
                logger.info("No error messages found in post modal")
            return False
        except WebDriverException:
            logger.info("Post modal no longer present, considering post successful")
        try:
            WebDriverWait(self.ui.driver, self.config.short_timeout).until(
                EC.presence_of_element_located((By.XPATH, VerifySelectors.CLOSED_SHARE_BOX))
            )
            logger.info("Back at feed with share box visible, post appears successful")
            try:
                snippet = (post_text or "").strip().split("\n")[0][:80]
                if snippet:
                    snippet_literal = snippet.replace('"', '\\"')
                    xpath = VerifySelectors.FEED_SNIPPET_TEMPLATE.format(snippet=snippet_literal)
                    WebDriverWait(self.ui.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    logger.info("Detected post content snippet in feed")
            except TimeoutException:
                logger.info("Could not confirm post content in feed; relying on toast/feed checks")
            return True
        except TimeoutException:
            logger.warning("Could not confirm post success with certainty")
            return False
        except WebDriverException as e:
            logger.error(f"Unexpected error during post success verification: {e.msg}")
            return False
