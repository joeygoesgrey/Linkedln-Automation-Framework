"""Selenium Chrome driver setup for LinkedIn automation.

WHY
  Keep driver launch logic in one place, so the browser can be tuned for
  LinkedIn's bot checks without touching the rest of the code.
"""

import logging
import os
import platform
import re
import shutil
import subprocess

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

# The package is an optional extra, so a missing install must not stop import.
try:
    import undetected_chromedriver as uc  # pyright: ignore[reportMissingImports]
except ImportError:
    uc = None

from laf.config import Config
from laf.errors import DriverError

logger = logging.getLogger(__name__)


class DriverFactory:
    """Provide static helpers that build a working Chrome driver.

    WHY
      Hide OS detection, browser lookup and the fallback chain behind one call,
      so the rest of the code never builds a driver itself.
    """

    @staticmethod
    def setup_driver(config: Config):
        """Return a Chrome driver that is ready for LinkedIn.

        WHY
          Keep driver setup in one method, so the launch order can be tuned when
          LinkedIn changes its bot checks.

        Args
          config: Config, the frozen settings for this run.

        Returns
          webdriver.Chrome, the first driver that starts.

        Raises
          DriverError: with CHROME_NOT_FOUND when no browser binary exists, or
            DRIVER_ALL_ATTEMPTS_FAILED when every launch fails.
        """
        try:
            # Detect OS platform
            system = platform.system()
            logger.info("Detected operating system: %s", system)

            # Different browser paths and commands based on OS
            browser_paths, version_commands = DriverFactory._get_platform_specific_paths(system)

            # Try to detect browser version
            browser_version = DriverFactory._detect_browser_version(version_commands)

            # Find the first existing browser path
            browser_path = DriverFactory._find_browser_path(browser_paths)
            if browser_path is None:
                raise DriverError("CHROME_NOT_FOUND")

            # Try multiple initialization strategies
            driver = DriverFactory._initialize_driver_with_fallbacks(
                browser_path, browser_version, config
            )

            logger.info("Successfully initialized ChromeDriver")
            return driver
        except DriverError:
            raise
        except (WebDriverException, OSError, ValueError) as error:
            raise DriverError("DRIVER_ALL_ATTEMPTS_FAILED") from error

    @staticmethod
    def _get_platform_specific_paths(system):
        """Return browser paths and version commands for the host OS.

        WHY
          Find the browser on Linux, macOS and Windows, so setup can pass an
          exact binary instead of guessing.

        Args
          system: str, the OS name from platform.system.

        Returns
          tuple[list[str], list[tuple[str, str]]], candidate binary paths and
          the command pairs used to read their versions.
        """
        if system == "Linux":
            browser_paths = ["/usr/bin/chromium", "/usr/bin/chrome", "/usr/bin/google-chrome"]
            version_commands = [("chromium", "--version"), ("google-chrome", "--version")]
        elif system == "Darwin":  # macOS
            browser_paths = [
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ]
            version_commands = [("Chromium", "--version"), ("Google Chrome", "--version")]
        elif system == "Windows":
            browser_paths = [
                os.path.expandvars("%ProgramFiles%\\Chromium\\Application\\chrome.exe"),
                os.path.expandvars("%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe"),
                os.path.expandvars("%ProgramFiles(x86)%\\Google\\Chrome\\Application\\chrome.exe"),
            ]
            version_commands = [("chromium", "--version"), ("chrome", "--version")]
        else:
            logger.warning("Unknown operating system: %s", system)
            browser_paths = []
            version_commands = []

        return browser_paths, version_commands

    @staticmethod
    def _detect_browser_version(version_commands):
        """Return the version text of the first browser that answers.

        WHY
          Know the browser major version, so a local chromedriver can be checked
          against it before use.

        Args
          version_commands: list[tuple[str, str]], command and argument pairs
            from _get_platform_specific_paths.

        Returns
          Optional[str], the version text, or None when no command answers.
        """
        browser_version = None
        for cmd, arg in version_commands:
            try:
                version_output = subprocess.check_output(
                    [cmd, arg], text=True, stderr=subprocess.STDOUT
                )
                browser_version = version_output.strip()
                logger.info("Browser version: %s", browser_version)
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue

        if not browser_version:
            logger.warning("Could not determine browser version")

        return browser_version

    @staticmethod
    def _find_browser_path(browser_paths):
        """Return the first browser binary that exists on disk.

        WHY
          Pass an explicit binary to Selenium, so setup still works when more
          than one browser is installed.

        Args
          browser_paths: list[str], candidate paths from
            _get_platform_specific_paths.

        Returns
          Optional[str], the first path that exists, or None when none does.
        """
        browser_path = None
        for path in browser_paths:
            if os.path.exists(path):
                browser_path = path
                logger.info("Found browser at: %s", browser_path)
                break
        return browser_path

    @staticmethod
    def _browser_arguments(config: Config):
        """Return the Chrome arguments shared by every launch attempt.

        WHY
          Give every fallback the same window, profile and headless settings, so
          the browser behaves the same whichever attempt wins.

        Args
          config: Config, the frozen settings for this run.

        Returns
          list[str], the Chrome command line arguments.

        MUTATIONS
          Creates config.user_data_dir on disk when it is set.
        """
        arguments = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-notifications",
            f"--window-size={config.window_size[0]},{config.window_size[1]}",
            f"user-agent={config.user_agent}",
        ]
        if config.headless:
            arguments.append("--headless=new")
        if config.user_data_dir:
            os.makedirs(config.user_data_dir, exist_ok=True)
            arguments.append(f"--user-data-dir={config.user_data_dir}")
            arguments.append("--profile-directory=Default")
        return arguments

    @staticmethod
    def _build_selenium_options(browser_path, config: Config):
        """Return a new Selenium options object for one attempt.

        WHY
          Give each attempt its own options, so a reused object cannot crash the
          next launch.

        Args
          browser_path: Optional[str], the browser binary path from setup, or None.
          config: Config, the frozen settings for this run.

        Returns
          webdriver.ChromeOptions, a new options object.
        """
        options = webdriver.ChromeOptions()
        if browser_path:
            options.binary_location = browser_path
        for argument in DriverFactory._browser_arguments(config):
            options.add_argument(argument)
        return options

    @staticmethod
    def _build_uc_options(browser_path, config: Config):
        """Return a new undetected-chromedriver options object.

        WHY
          Build the options class that undetected-chromedriver needs, since it
          cannot share one with plain Selenium.

        Args
          browser_path: Optional[str], the browser binary path from setup, or None.
          config: Config, the frozen settings for this run.

        Returns
          uc.ChromeOptions, a new options object.

        Raises
          DriverError: with DRIVER_OPTIONAL_PACKAGE_MISSING when
            undetected-chromedriver is not installed.
        """
        if uc is None:
            raise DriverError("DRIVER_OPTIONAL_PACKAGE_MISSING", package="undetected-chromedriver")
        options = uc.ChromeOptions()
        if browser_path:
            options.binary_location = browser_path
        for argument in DriverFactory._browser_arguments(config):
            options.add_argument(argument)
        return options

    @staticmethod
    def _major_version(text):
        """Return the major number from a version string.

        WHY
          Compare driver and browser by major version only, since that is the
          part that has to match.

        Args
          text: Optional[str], version output such as "ChromeDriver 147.0.7727.101".

        Returns
          Optional[str], the major version, or None when no version is present.
        """
        if not text:
            return None
        match = re.search(r"(\d+)\.\d+", text)
        return match.group(1) if match else None

    @staticmethod
    def _driver_matches(driver_path, browser_version):
        """Say whether a local chromedriver matches the browser major version.

        WHY
          Reject a mismatched local driver before use, so setup moves to the next
          attempt instead of failing with a long trace.

        Args
          driver_path: str, the chromedriver binary path from
            _find_local_chromedriver.
          browser_version: Optional[str], the version text from
            _detect_browser_version.

        Returns
          bool, true when the two major versions match.
        """
        try:
            output = subprocess.check_output(
                [driver_path, "--version"],
                text=True,
                stderr=subprocess.STDOUT,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return DriverFactory._major_version(output) == DriverFactory._major_version(browser_version)

    @staticmethod
    def _initialize_driver_with_fallbacks(browser_path, browser_version, config: Config):
        """Return the first launch strategy that starts a driver.

        WHY
          Survive a driver and browser version drift, so setup reaches a working
          driver instead of stopping at the first mismatch. The real order is: a
          matching local chromedriver, then webdriver-manager, then
          undetected-chromedriver when it is installed, then Selenium Manager.

        Args
          browser_path: str, the browser binary path from setup.
          browser_version: Optional[str], the version text from
            _detect_browser_version.
          config: Config, the frozen settings for this run.

        Returns
          webdriver.Chrome, the first driver that starts.

        Raises
          DriverError: with DRIVER_ALL_ATTEMPTS_FAILED when every strategy fails.
        """
        attempts = []

        local_driver = DriverFactory._find_local_chromedriver()
        if local_driver and DriverFactory._driver_matches(local_driver, browser_version):
            try:
                logger.info("Using local chromedriver at %s", local_driver)
                return webdriver.Chrome(
                    service=Service(local_driver),
                    options=DriverFactory._build_selenium_options(browser_path, config),
                )
            except (WebDriverException, OSError) as error:
                attempts.append(("local", str(error)[:200]))
        elif local_driver:
            logger.info(
                "Ignoring local chromedriver at %s: its version does not match the browser",
                local_driver,
            )

        try:
            logger.info("Resolving a matching driver with webdriver-manager")
            chrome_type = (
                ChromeType.CHROMIUM
                if "chromium" in (browser_path or "").lower()
                else ChromeType.GOOGLE
            )
            driver_path = ChromeDriverManager(chrome_type=chrome_type).install()
            return webdriver.Chrome(
                service=Service(driver_path),
                options=DriverFactory._build_selenium_options(browser_path, config),
            )
        except (WebDriverException, OSError, ValueError) as error:
            attempts.append(("webdriver-manager", str(error)[:200]))

        if uc is not None:
            try:
                logger.info("Trying undetected-chromedriver")
                return uc.Chrome(
                    options=DriverFactory._build_uc_options(browser_path, config),
                    use_subprocess=True,
                    browser_executable_path=browser_path,
                )
            except (WebDriverException, OSError) as error:
                attempts.append(("undetected-chromedriver", str(error)[:200]))

        try:
            logger.info("Trying Selenium Manager")
            return webdriver.Chrome(
                options=DriverFactory._build_selenium_options(browser_path, config)
            )
        except (WebDriverException, OSError) as error:
            attempts.append(("selenium-manager", str(error)[:200]))

        logger.error("All driver attempts failed: %s", attempts)
        raise DriverError("DRIVER_ALL_ATTEMPTS_FAILED")

    @staticmethod
    def _find_local_chromedriver():
        """Return an existing local chromedriver binary.

        WHY
          Prefer a driver already on the machine, so start-up skips a download.

        Returns
          Optional[str], the first binary found in an env var, PATH, or a common
          location, or None when none exists.
        """
        # 1) Explicit env var
        for env_name in ("CHROMEDRIVER_PATH", "CHROMEWEBDRIVER", "WEBDRIVER_CHROME_DRIVER"):
            path = os.getenv(env_name)
            if path and os.path.exists(path):
                return path
        # 2) In PATH
        path = shutil.which("chromedriver")
        if path:
            return path
        # 3) Common locations
        common_paths = [
            "/usr/bin/chromedriver",
            "/usr/local/bin/chromedriver",
            "/snap/bin/chromedriver",
        ]
        for p in common_paths:
            if os.path.exists(p):
                return p
        return None
