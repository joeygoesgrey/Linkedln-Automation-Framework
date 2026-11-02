"""Selectors used during the login and 2FA process.

WHY
  Serve the sign in and 2FA pages, so a login page change can be fixed without
  touching any other page.
"""

from selenium.webdriver.common.by import By


class LoginSelectors:
    """Selectors used during the login and 2FA process.

    WHY
      Serve the sign in form, the 2FA pin field and the logged in check, so a
      login page change has one file to update.
    """

    SIGN_IN_LINK = "a[href*='signin']"  # linkedin_ui/login.py:68
    USERNAME_FIELDS = [
        "input#username",
        "input[name='session_key']",
        "input[autocomplete*='username']",
        "input[type='email']",
        (By.XPATH, "//input[@type='email' or contains(@autocomplete, 'username')]"),
    ]  # linkedin_ui/login.py:81
    PASSWORD_FIELDS = [
        "input#password",
        "input[name='session_password']",
        "input[autocomplete*='current-password']",
        "input[type='password']",
        (By.XPATH, "//input[@type='password' or contains(@autocomplete, 'password')]"),
    ]  # linkedin_ui/login.py:100
    SUBMIT_BUTTONS = [
        "button[type='submit']",
        "button.sign-in-form__submit-button",
        "button[data-litms-control-urn='login-submit']",
        (By.XPATH, "//button[.//span[normalize-space()='Sign in']]"),
    ]  # linkedin_ui/login.py:113
    VERIFICATION_PIN = "input#input__phone_verification_pin"  # linkedin_ui/login.py:128

    SUCCESS_INDICATORS = [
        (By.CSS_SELECTOR, "div.feed-identity-module"),
        (By.CSS_SELECTOR, "button[data-control-name='create_post']"),
        (By.XPATH, "//button[contains(.,'Start a post')]"),
        (By.CSS_SELECTOR, "div.share-box-feed-entry__avatar"),
    ]  # linkedin_ui/login.py:135
