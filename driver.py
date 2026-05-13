"""Resilient Selenium driver initialisation helpers for LinkedIn automation.

Why:
    LinkedIn frequently tightens bot detection; abstracting driver setup allows
    us to tweak launch strategies centrally.

When:
    Imported during bot instantiation to obtain a configured Chrome/Chromium
    WebDriver capable of bypassing common detection heuristics.

How:
    Detects platform specifics, attempts multiple driver strategies (local
    binaries, undetected-chromedriver, webdriver-manager), and returns a ready
    driver instance.
"""

import os
import platform
import logging
import shutil
import subprocess
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.chrome import ChromeType

import config


class DriverFactory:
    """Factory utilities for provisioning Chrome-based Selenium drivers.

    Why:
        Encapsulate OS detection, binary discovery, and fallback strategies so
        the rest of the codebase simply calls :meth:`setup_driver`.

    When:
        Invoked whenever a new automation session begins.

    How:
        Offers static helpers that search for browser binaries, configure
        options, and cascade through multiple launch strategies until a driver
        succeeds or all attempts fail.
    """

    @staticmethod
    def setup_driver():
        """Provision a Selenium WebDriver resilient to LinkedIn bot detection.

        Why:
            LinkedIn frequently changes detection heuristics; wrapping setup in
            a single method allows us to tune the launch sequence quickly.

        When:
            Called during :class:`LinkedInBot` construction before any LinkedIn
            page is accessed.

        How:
            Detects the host OS, resolves browser paths/versions, configures
            undetected-chromedriver options, and sequentially tries local
            chromedriver, undetected-chromedriver, and webdriver-manager
            fallbacks, returning the first successful driver.

        Returns:
            webdriver.Chrome: A configured Chrome or Chromium Selenium driver.

        Raises:
            Exception: Propagates when every initialisation strategy fails.
        """
        try:
            # Detect OS platform
            system = platform.system()
            logging.info(f"Detected operating system: {system}")
            
            # Different browser paths and commands based on OS
            browser_paths, version_commands = DriverFactory._get_platform_specific_paths(system)
            
            # Try to detect browser version
            browser_version = DriverFactory._detect_browser_version(version_commands)
            
            # Find the first existing browser path
            browser_path = DriverFactory._find_browser_path(browser_paths)
            
            # Configure undetected-chromedriver options
            options = DriverFactory._configure_browser_options()
            
            # Try multiple initialization strategies
            driver = DriverFactory._initialize_driver_with_fallbacks(browser_path, browser_version, options)
            
            logging.info("Successfully initialized ChromeDriver")
            return driver
        except Exception as e:
            logging.error(f"All ChromeDriver initialization attempts failed: {str(e)}")
            raise
            
    @staticmethod
    def _get_platform_specific_paths(system):
        """Derive candidate browser binaries and version commands per OS.

        Why:
            Chrome/Chromium installs vary by platform; providing tailored search
            paths improves the odds of finding the browser.

        When:
            Executed early in :meth:`setup_driver` prior to driver initialisation.

        How:
            Returns platform-specific tuples containing likely executable paths
            and corresponding ``--version`` commands.

        Args:
            system (str): OS name from :func:`platform.system`.

        Returns:
            tuple[list[str], list[tuple[str, str]]]: Candidate paths and version
            command pairs.
        """
        if system == "Linux":
            browser_paths = ["/usr/bin/chromium", "/usr/bin/chrome", "/usr/bin/google-chrome"]
            version_commands = [("chromium", "--version"), ("google-chrome", "--version")]
        elif system == "Darwin":  # macOS
            browser_paths = [
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            ]
            version_commands = [("Chromium", "--version"), ("Google Chrome", "--version")]
        elif system == "Windows":
            browser_paths = [
                os.path.expandvars("%ProgramFiles%\\Chromium\\Application\\chrome.exe"),
                os.path.expandvars("%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe"),
                os.path.expandvars("%ProgramFiles(x86)%\\Google\\Chrome\\Application\\chrome.exe")
            ]
            version_commands = [("chromium", "--version"), ("chrome", "--version")]
        else:
            logging.warning(f"Unknown operating system: {system}")
            browser_paths = []
            version_commands = []
        
        return browser_paths, version_commands
            
    @staticmethod
    def _detect_browser_version(version_commands):
        """Probe available browsers to retrieve a version string.

        Why:
            Some driver strategies need the installed browser version to select
            matching binaries.

        When:
            Called from :meth:`setup_driver` after collecting platform-specific
            commands.

        How:
            Iterates over command tuples, runs them via ``subprocess``, and
            returns the first successful output.

        Args:
            version_commands (list[tuple[str, str]]): Command/argument pairs to
                execute.

        Returns:
            str | None: Detected version string or ``None`` when detection fails.
        """
        browser_version = None
        for cmd, arg in version_commands:
            try:
                version_output = subprocess.check_output([cmd, arg], text=True, stderr=subprocess.STDOUT)
                browser_version = version_output.strip()
                logging.info(f"Browser version: {browser_version}")
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        if not browser_version:
            logging.warning("Could not determine browser version")
            
        return browser_version
    
    @staticmethod
    def _find_browser_path(browser_paths):
        """Locate the first existing browser executable from candidate paths.

        Why:
            Passing an explicit binary to Selenium improves reliability when
            multiple versions coexist.

        When:
            Executed during driver setup after gathering OS-specific locations.

        How:
            Iterates over supplied paths and returns the first that exists on the
            filesystem.

        Args:
            browser_paths (list[str]): Candidate absolute paths.

        Returns:
            str | None: Resolved path or ``None`` if none are present.
        """
        browser_path = None
        for path in browser_paths:
            if os.path.exists(path):
                browser_path = path
                logging.info(f"Found browser at: {browser_path}")
                break
        return browser_path
    
    @staticmethod
    def _configure_browser_options():
        """Build Chrome options tuned for automation while mimicking humans.

        Why:
            Applying consistent arguments (headless toggles, window sizing,
            custom UA) reduces flakiness and detection likelihood.

        When:
            Called before any driver initialisation strategy is attempted.

        How:
            Creates :class:`uc.ChromeOptions`, applies sandbox, headless, window,
            and notification arguments based on config.

        Returns:
            uc.ChromeOptions: Options object ready for driver creation.
        """
        options = uc.ChromeOptions()
        
        # Basic configuration
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        # Apply headless mode if configured
        if config.HEADLESS:
            options.add_argument("--headless")
            
        # Set window size
        options.add_argument(f"--window-size={config.WINDOW_SIZE[0]},{config.WINDOW_SIZE[1]}")
        
        # Disable notifications and add custom user agent
        options.add_argument("--disable-notifications")
        options.add_argument(f"user-agent={config.USER_AGENT}")
        
        # Add persistent profile to save login session
        if config.USER_DATA_DIR:
            os.makedirs(config.USER_DATA_DIR, exist_ok=True)
            options.add_argument(f"--user-data-dir={config.USER_DATA_DIR}")
            options.add_argument("--profile-directory=Default")
        
        return options
    
    @staticmethod
    def _initialize_driver_with_fallbacks(browser_path, browser_version, options):
        """Attempt multiple driver launch strategies until one succeeds.

        Why:
            Different environments require different launch paths; chaining
            fallbacks maximises success without manual intervention.

        When:
            Called from :meth:`setup_driver` after collecting platform details
            and options.

        How:
            Tries local chromedriver, undetected-chromedriver (two variants),
            and webdriver-manager, returning as soon as a driver initialises.

        Args:
            browser_path (str | None): Preferred browser binary path.
            browser_version (str | None): Detected browser version string.
            options (uc.ChromeOptions): Preconfigured options for launch.

        Returns:
            webdriver.Chrome: Successfully initialised driver instance.

        Raises:
            Exception: Propagated when all strategies fail.
        """

        # 0) Prefer a locally installed chromedriver to avoid network
        local_driver_path = DriverFactory._find_local_chromedriver()
        if local_driver_path:
            try:
                logging.info(f"Attempting local ChromeDriver at: {local_driver_path}")
                # Build standard ChromeOptions mirroring our settings
                std_options = webdriver.ChromeOptions()
                std_options.add_argument("--no-sandbox")
                std_options.add_argument("--disable-dev-shm-usage")
                if config.HEADLESS:
                    std_options.add_argument("--headless=new")
                std_options.add_argument(f"--window-size={config.WINDOW_SIZE[0]},{config.WINDOW_SIZE[1]}")
                std_options.add_argument("--disable-notifications")
                std_options.add_argument(f"user-agent={config.USER_AGENT}")
                if config.USER_DATA_DIR:
                    std_options.add_argument(f"--user-data-dir={config.USER_DATA_DIR}")
                    std_options.add_argument("--profile-directory=Default")
                # If we detected a browser binary, point to it
                if browser_path:
                    try:
                        std_options.binary_location = browser_path
                    except Exception:
                        pass
                service = Service(local_driver_path)
                driver = webdriver.Chrome(service=service, options=std_options)
                return driver
            except Exception as e_local:
                logging.warning(f"Local ChromeDriver init failed: {e_local}")

        # 1) Try undetected-chromedriver (may require network for patching)
        try:
            logging.info("Attempting to use undetected-chromedriver (system/auto)")
            driver_args = {
                "options": options,
                "use_subprocess": True,
                "driver_executable_path": False
            }
            if browser_path:
                driver_args["browser_executable_path"] = browser_path
            driver = uc.Chrome(**driver_args)
            return driver
        except Exception as e1:
            logging.warning(f"undetected-chromedriver init failed: {str(e1)}. Retrying with default.")

            # 2) Retry default undetected-chromedriver init
            try:
                logging.info("Attempting default undetected-chromedriver initialization")
                driver_args = {
                    "options": options,
                    "use_subprocess": True
                }
                if browser_path:
                    driver_args["browser_executable_path"] = browser_path
                driver = uc.Chrome(**driver_args)
                return driver
            except Exception as e2:
                logging.warning(f"Second undetected-chromedriver init failed: {str(e2)}. Trying Selenium Manager (may need network).")

                # 3) Selenium Manager via webdriver-manager (requires network)
                logging.info("Attempting fallback to standard selenium ChromeDriver via webdriver-manager")
                chrome_type = ChromeType.CHROMIUM if browser_version and "chromium" in str(browser_version).lower() else ChromeType.GOOGLE
                logging.info(f"Using ChromeType: {chrome_type}")
                service = Service(ChromeDriverManager(chrome_type=chrome_type).install())
                driver = webdriver.Chrome(service=service, options=options)
                return driver

    @staticmethod
    def _find_local_chromedriver():
        """Search common locations for an existing chromedriver binary.

        Why:
            Using a local binary avoids network downloads and speeds up start-up.

        When:
            Invoked prior to falling back to undetected-chromedriver or
            webdriver-manager.

        How:
            Checks environment variables, PATH, and common installation paths
            and returns the first binary discovered.

        Returns:
            str | None: Path to chromedriver or ``None`` when not found.
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
