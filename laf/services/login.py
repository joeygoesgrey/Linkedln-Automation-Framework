"""Sign in to LinkedIn through the login form.

WHY
  Keep authentication in one place so every other service can assume the
  browser already has a live LinkedIn session.
"""

import logging

from pydantic import ValidationError
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from laf.config import Config
from laf.models import LoginModel
from laf.selectors.login import LoginSelectors

from ..ui import UiActions

logger = logging.getLogger(__name__)

class LoginService:
    """Sign the browser session in to LinkedIn with the stored credentials.

    WHY
      Leave the caller with a usable session, or a clear False, without each
      workflow repeating the form steps.
    """

    def __init__(self, ui: UiActions, config: Config) -> None:
        """
        WHY
          Give the login flow the shared driver, pacing helpers and the
          credential settings it needs to sign in.

        Args
          ui: UiActions, the shared Selenium action helper.
          config: Config, the frozen runtime settings.

        MUTATIONS
          Stores the driver helper and settings on the instance.
        """
        self.ui = ui
        self.config = config

    def login(self) -> bool:
        """Sign in with the configured credentials and report whether it worked.

        WHY
          Most downstream actions need a live session, and a returned False
          lets the caller stop instead of running into a login wall.

        Returns
          bool, True when LinkedIn shows the feed or a success indicator, False
          when a field or button is missing, credentials fail validation, or a
          verification code is required.
        """
        try:
            self.ui.driver.get(self.config.linkedin_base_url)
            logger.info("Navigating to LinkedIn login page")
            self.ui.pause(self.config.min_page_load_delay, self.config.max_page_load_delay)

            try:
                if "feed" in self.ui.driver.current_url.lower():
                    logger.info("Already logged in to LinkedIn")
                    return True
            except WebDriverException:
                pass

            try:
                sign_in_button = WebDriverWait(self.ui.driver, self.config.short_timeout).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, LoginSelectors.SIGN_IN_LINK))
                )
                sign_in_button.click()
                logger.info("Clicked sign-in button")
                self.ui.pause()
            except (TimeoutException, WebDriverException):
                logger.info("No sign-in button found, likely already on login page")

            if not any(x in self.ui.driver.current_url.lower() for x in ["login", "signin"]):
                logger.warning(f"Not on login page. Current URL: {self.ui.driver.current_url}")
                self.ui.driver.get(self.config.linkedin_login_url)
                self.ui.pause()

            username_selectors = LoginSelectors.USERNAME_FIELDS
            username_field = self.ui.find_by_selectors(
                username_selectors, By.CSS_SELECTOR, timeout=self.config.element_timeout
            )
            if not username_field:
                logger.error("Could not find username field")
                return False

            username = self.config.linkedin_username
            password = self.config.linkedin_password

            # Pydantic validation (Standard 3)
            try:
                validated = LoginModel(username=username or "", password=password or "")
            except ValidationError as e:
                logger.error(f"Credential validation failed: {e}")
                return False

            username = validated.username
            password = validated.password

            self.ui.pause(0.5, 1.5)
            self.ui.type_with_delays(username_field, username)

            password_selectors = LoginSelectors.PASSWORD_FIELDS
            password_field = self.ui.find_by_selectors(
                password_selectors, By.CSS_SELECTOR, timeout=self.config.element_timeout
            )
            if not password_field:
                logger.error("Could not find password field")
                return False

            self.ui.pause(0.5, 1)
            self.ui.type_with_delays(password_field, password)

            sign_in_selectors = LoginSelectors.SUBMIT_BUTTONS
            sign_in_btn = self.ui.find_by_selectors(
                sign_in_selectors, By.CSS_SELECTOR, timeout=self.config.element_timeout
            )
            if not sign_in_btn:
                logger.error("Could not find sign-in button")
                return False
            sign_in_btn.click()
            logger.info("Clicked login button")
            self.ui.pause(3, 5)

            try:
                WebDriverWait(self.ui.driver, self.config.short_timeout).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, LoginSelectors.VERIFICATION_PIN)
                    )
                )
                logger.warning("Verification code required. Check your phone.")
                return False
            except TimeoutException:
                logger.info("Verification code not required or error occurred.")

            success_indicators = LoginSelectors.SUCCESS_INDICATORS
            for selector_type, selector in success_indicators:
                try:
                    WebDriverWait(self.ui.driver, self.config.element_timeout).until(
                        EC.presence_of_element_located((selector_type, selector))
                    )
                    logger.info("Successfully logged in to LinkedIn")
                    return True
                except TimeoutException:
                    continue

            if "feed" in self.ui.driver.current_url.lower():
                logger.info("Successfully logged in to LinkedIn (URL check)")
                return True

            logger.error(f"Login might have failed. Current URL: {self.ui.driver.current_url}")
            return False
        except WebDriverException as e:
            logger.error(f"Login failed: {e.msg}", exc_info=True)
            return False
