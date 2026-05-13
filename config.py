"""Centralised configuration for the LinkedIn automation bot.

Why:
    Keep secrets, selectors, runtime toggles, and logging conventions in a
    single module so the rest of the codebase can import consistent defaults.

When:
    Imported at startup by CLI scripts, automation classes, and helper modules
    needing environment-derived values or shared constants.

How:
    Loads environment variables via ``python-dotenv``, exposes typed constants
    for credentials, AI settings, Selenium timeouts, and logging, and provides
    helper functions for safe casting and logging configuration.
"""

import os
import logging
import pathlib
from datetime import datetime
from dotenv import load_dotenv
from ui_selectors import ComposerSelectors

# Load environment variables
load_dotenv()

# LinkedIn credentials
LINKEDIN_USERNAME = os.getenv("LINKEDIN_USERNAME")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

# OpenAI settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Project marketing defaults
MARKETING_MODE = os.getenv("MARKETING_MODE", "true").lower() == "true"
PROJECT_NAME = os.getenv("PROJECT_NAME", "LinkedIn Bot")
PROJECT_URL = os.getenv("PROJECT_URL", "https://github.com/joeygoesgrey/linkedln-bot")
PROJECT_PITCH = os.getenv("PROJECT_PITCH", "Human-like LinkedIn automation that posts, schedules, uploads media, tags people, and runs AI-powered engagement loops with detailed logging.")
PROJECT_SHORT_PITCH = os.getenv("PROJECT_SHORT_PITCH", "Open-source LinkedIn automation toolkit for human-like posting and AI engagement.")
PROJECT_CONTEXT = os.getenv("PROJECT_CONTEXT", "LinkedIn Bot is an MIT-licensed automation toolkit that drives the LinkedIn web UI with Selenium, supports posting, scheduling, media uploads, and mentions, and uses OpenAI/Gemini for AI-assisted engagement while logging every step and respecting human-like pacing.")
PROJECT_TAGLINE = os.getenv("PROJECT_TAGLINE", f"{PROJECT_PITCH} Grab the code: {PROJECT_URL}")

# Browser settings
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"  # Run browser in headless mode, can be overridden
WINDOW_SIZE = (1920, 1080)  # Browser window size
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
USER_DATA_DIR = os.getenv("USER_DATA_DIR", os.path.join(os.getcwd(), "chrome_profile"))

# URLs
LINKEDIN_BASE_URL = "https://www.linkedin.com/"
LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"
LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login/"

# Delays (in seconds)
MIN_TYPING_DELAY = 0.05  # Minimum delay between key presses
MAX_TYPING_DELAY = 0.15  # Maximum delay between key presses
MIN_ACTION_DELAY = 1     # Minimum delay between actions
MAX_ACTION_DELAY = 3     # Maximum delay between actions
MIN_PAGE_LOAD_DELAY = 2  # Minimum delay after page load
MAX_PAGE_LOAD_DELAY = 5  # Maximum delay after page load

# Selenium timeouts
ELEMENT_TIMEOUT = 10  # Maximum wait time for elements to appear (seconds)
SHORT_TIMEOUT = 5     # Shorter timeout for quick checks

# File paths
DEFAULT_TOPIC_FILE = "Topics.txt"
LOG_DIRECTORY = "logs"
CUSTOM_POSTS_FILE = os.getenv("CUSTOM_POSTS_FILE", "CustomPosts.txt")

# Content limits
MAX_POST_LENGTH = 1300
ENABLE_TEXT_PREPROCESSING = os.getenv("ENABLE_TEXT_PREPROCESSING", "false").lower() == "true"
SUMMARIZE_INPUT = os.getenv("SUMMARIZE_INPUT", "false").lower() == "true"

def _safe_float(value: str | None, default: float) -> float:
    """Convert an environment value to ``float`` with a resilient fallback.

    Why:
        Environment configuration often arrives as strings; this helper avoids
        repetitive try/except blocks throughout the module.

    When:
        Used during module import when computing float-based settings such as
        summarisation ratios.

    How:
        Attempts to cast ``value`` to ``float`` and returns ``default`` when the
        value is ``None`` or malformed.

    Args:
        value (str | None): Raw environment string to convert.
        default (float): Fallback value when conversion fails.

    Returns:
        float: Converted number or the provided default.
    """

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: str | None, default: int) -> int:
    """Convert an environment value to ``int`` with a resilient fallback.

    Why:
        Many runtime limits (token counts, char caps) are numeric but configured
        as strings; this helper standardises conversion and error handling.

    When:
        Called during module initialisation while populating integer constants.

    How:
        Attempts to cast ``value`` to ``int`` and returns ``default`` when the
        cast fails or the value is ``None``.

    Args:
        value (str | None): Raw environment string to convert.
        default (int): Fallback to use when conversion fails.

    Returns:
        int: Converted integer or the provided default.
    """

    try:
        return int(value)
    except (TypeError, ValueError):
        return default

SUMMARIZE_RATIO = _safe_float(os.getenv("SUMMARIZE_RATIO"), 0.3)
MAX_INPUT_CHARS = _safe_int(os.getenv("MAX_INPUT_CHARS"), 3200)
CAPTURE_TYPEAHEAD_HTML = os.getenv("CAPTURE_TYPEAHEAD_HTML", "false").lower() == "true"
TYPEAHEAD_CAPTURE_DIR = os.getenv(
    "TYPEAHEAD_CAPTURE_DIR",
    str(pathlib.Path(LOG_DIRECTORY) / "typeahead")
)


# LinkedIn selectors (can be updated if the UI changes)
START_POST_SELECTORS = ComposerSelectors.START_POST_TRIGGERS
POST_EDITOR_SELECTORS = ComposerSelectors.POST_EDITOR
POST_BUTTON_SELECTORS = ComposerSelectors.POST_BUTTON

# Default logging configuration
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

def configure_logging(log_level=None):
    """Initialise console and file logging for the automation suite.

    Why:
        Consistent logging is critical for diagnosing flaky UI interactions.
        Centralising setup ensures every script emits structured output.

    When:
        Called on module import with defaults and invoked again by the CLI
        entrypoint when the user requests ``--debug`` verbosity.

    How:
        Ensures the logs directory exists, creates a timestamped log file, and
        configures :mod:`logging` handlers for both file and stdout streams.

    Args:
        log_level (int | None): Explicit logging level; defaults to
            :data:`DEFAULT_LOG_LEVEL` when ``None``.

    Returns:
        None
    """
    level = log_level or DEFAULT_LOG_LEVEL

    # Ensure log directory exists
    log_dir = pathlib.Path(LOG_DIRECTORY)
    log_dir.mkdir(exist_ok=True)

    # Create unique log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"linkedin_bot_{timestamp}.log"

    # Configure logging to both file and console
    logging.basicConfig(
        level=level,
        format=DEFAULT_LOG_FORMAT,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    logging.info(f"Logging configured at level {logging.getLevelName(level)}")
    logging.info(f"Log file: {log_file}")

# Initialize logging with default configuration
configure_logging()
