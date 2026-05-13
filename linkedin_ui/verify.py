"""Mix-in utilities for verifying post submission success.

Why:
    Ensure automation detects failures promptly rather than assuming success.

When:
    Used after submitting a post or schedule action through the composer.

How:
    Checks for toasts, absence of modals, and presence of feed indicators.
"""

import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import config
from ui_selectors import VerifySelectors


class VerifyMixin:
    """Expose helpers to confirm post submission status.

    Why:
        Ensures automation can differentiate between success and silent failure.

    When:
        Mixed into :class:`LinkedInInteraction` and used after posting or scheduling actions.

    How:
        Provides :meth:`_verify_post_success` which inspects toasts, modal states, and feed snippets.
    """
    def _verify_post_success(self, post_text):
        """Inspect the UI to determine whether a post was successfully submitted.

        Why:
            Allows the automation to confirm success and log appropriate feedback.

        When:
            Called immediately after attempting to post or schedule content.

        How:
            Looks for success toasts, ensures the composer closes, and optionally
            verifies the post snippet appears in the feed.

        Args:
            post_text (str): Original content to help identify feed entries.

        Returns:
            bool: ``True`` if success indicators appear, ``False`` otherwise.
        """

        logging.info("Verifying post success...")
        time.sleep(3)
        success_indicators = VerifySelectors.SUCCESS_INDICATORS
        for selector in success_indicators:
            try:
                WebDriverWait(self.driver, config.SHORT_TIMEOUT).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                logging.info(f"Found success indicator: {selector}")
                break
            except Exception:
                continue
        try:
            post_modal = self.driver.find_element(
                By.XPATH, VerifySelectors.POST_MODAL
            )
            logging.info("Post modal still exists, post might not be complete")
            try:
                error_message = post_modal.find_element(
                    By.XPATH, VerifySelectors.POST_MODAL_ERROR
                )
                error_text = error_message.text.strip()
                logging.error(f"Error message found in post modal: {error_text}")
                return False
            except Exception:
                logging.info("No error messages found in post modal")
            return False
        except Exception:
            logging.info("Post modal no longer present, considering post successful")
        try:
            WebDriverWait(self.driver, config.SHORT_TIMEOUT).until(
                EC.presence_of_element_located((By.XPATH, VerifySelectors.CLOSED_SHARE_BOX))
            )
            logging.info("Back at feed with share box visible, post appears successful")
            try:
                snippet = (post_text or "").strip().split("\n")[0][:80]
                if snippet:
                    snippet_literal = snippet.replace('"', '\\"')
                    xpath = VerifySelectors.FEED_SNIPPET_TEMPLATE.format(snippet=snippet_literal)
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    logging.info("Detected post content snippet in feed")
            except Exception:
                logging.info("Could not confirm post content in feed; relying on toast/feed checks")
            return True
        except TimeoutException:
            logging.warning("Could not confirm post success with certainty")
            return False
        except Exception as e:
            logging.error(f"Unexpected error during post success verification: {e}")
            return False
