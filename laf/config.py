"""Centralised configuration for the LinkedIn automation bot.

WHY
  Keep secrets, runtime toggles and shared defaults in one module so the rest
  of the codebase reads one snapshot of them, read once at import time.
"""

import logging
import os
import pathlib
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

_DEFAULT_PROJECT_PITCH = (
    "Human-like LinkedIn automation that posts, schedules, uploads media, tags people, "
    "and runs AI-powered engagement loops with detailed logging."
)
_DEFAULT_PROJECT_SHORT_PITCH = (
    "Open-source LinkedIn automation toolkit for human-like posting and AI engagement."
)
_DEFAULT_PROJECT_CONTEXT = (
    "LinkedIn Bot is an MIT-licensed automation toolkit that drives the LinkedIn web UI "
    "with Selenium, supports posting, scheduling, media uploads, and mentions, and uses "
    "OpenAI/Gemini for AI-assisted engagement while logging every step and respecting "
    "human-like pacing."
)
_DEFAULT_PROJECT_URL = "https://github.com/joeygoesgrey/linkedln-bot"


@dataclass(frozen=True)
class Config:
    """Frozen snapshot of every runtime setting read at import time.

    WHY
      Give every caller one immutable set of settings, so no code can change a
      value after startup and tests can build the same shape from a plain dict.
    """

    linkedin_username: str | None
    linkedin_password: str | None
    openai_api_key: str | None
    openai_model: str
    marketing_mode: bool
    project_name: str
    project_url: str
    project_pitch: str
    project_short_pitch: str
    project_context: str
    project_tagline: str
    headless: bool
    window_size: tuple[int, int]
    user_agent: str
    user_data_dir: str
    linkedin_base_url: str
    linkedin_feed_url: str
    linkedin_login_url: str
    min_typing_delay: float
    max_typing_delay: float
    min_action_delay: int
    max_action_delay: int
    min_page_load_delay: int
    max_page_load_delay: int
    element_timeout: int
    short_timeout: int
    default_topic_file: str
    log_directory: str
    custom_posts_file: str
    max_post_length: int
    enable_text_preprocessing: bool
    summarize_input: bool
    summarize_ratio: float
    max_input_chars: int
    capture_typeahead_html: bool
    typeahead_capture_dir: str


def _safe_float(value: str | None, default: float) -> float:
    """Convert an environment value to ``float`` with a resilient fallback.

    WHY
      Environment settings arrive as strings, so cast them once here and fall
      back to the default instead of failing module import on a bad value.

    Args
      value: str | None, the raw environment string.
      default: float, the value to use when the cast fails or value is None.

    Returns
      float, the converted number or the default.
    """

    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning("Invalid float value %r, using default %r", value, default)
        return default


def _safe_int(value: str | None, default: int) -> int:
    """Convert an environment value to ``int`` with a resilient fallback.

    WHY
      Numeric limits are configured as strings, so cast them once here and
      fall back to the default instead of failing module import on a bad value.

    Args
      value: str | None, the raw environment string.
      default: int, the value to use when the cast fails or value is None.

    Returns
      int, the converted integer or the default.
    """

    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid integer value %r, using default %r", value, default)
        return default


def _safe_bool(value: str | None, default: bool) -> bool:
    """
    WHY
      Turn a raw environment string into a flag so toggles like HEADLESS and
      MARKETING_MODE keep their old "true in any case, everything else false"
      rule instead of leaking strings into runtime checks.

    Args
      value: str | None, the raw value read from the environment mapping.
      default: bool, the flag to use when the key is absent.

    Returns
      bool, True only when the value spells "true" in any letter case.
    """

    if value is None:
        return default
    return value.lower() == "true"


def load_config(
    env: Mapping[str, str] | None = None,
    headless_override: bool | None = None,
) -> Config:
    """
    WHY
      Build one immutable snapshot of every setting so callers get the same
      values from a plain dict in tests as from the real environment, and so no
      code can change a setting after startup.

    Args
      env: Mapping[str, str] | None, the environment source; defaults to
        os.environ when None.
      headless_override: bool | None, when set it wins over the HEADLESS value
        found in env.

    Returns
      Config, the frozen settings instance. The USER_DATA_DIR default is built
      from os.getcwd() once, at this call.
    """

    source: Mapping[str, str] = os.environ if env is None else env

    project_url = source.get("PROJECT_URL", _DEFAULT_PROJECT_URL)
    project_pitch = source.get("PROJECT_PITCH", _DEFAULT_PROJECT_PITCH)
    project_tagline = source.get(
        "PROJECT_TAGLINE", f"{project_pitch} Grab the code: {project_url}"
    )

    headless = _safe_bool(source.get("HEADLESS"), True)
    if headless_override is not None:
        headless = headless_override

    log_directory = "logs"

    return Config(
        linkedin_username=source.get("LINKEDIN_USERNAME"),
        linkedin_password=source.get("LINKEDIN_PASSWORD"),
        openai_api_key=source.get("OPENAI_API_KEY"),
        openai_model=source.get("OPENAI_MODEL", "gpt-4o-mini"),
        marketing_mode=_safe_bool(source.get("MARKETING_MODE"), True),
        project_name=source.get("PROJECT_NAME", "LinkedIn Bot"),
        project_url=project_url,
        project_pitch=project_pitch,
        project_short_pitch=source.get(
            "PROJECT_SHORT_PITCH", _DEFAULT_PROJECT_SHORT_PITCH
        ),
        project_context=source.get("PROJECT_CONTEXT", _DEFAULT_PROJECT_CONTEXT),
        project_tagline=project_tagline,
        headless=headless,
        window_size=(1920, 1080),
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36"
        ),
        user_data_dir=source.get(
            "USER_DATA_DIR", os.path.join(os.getcwd(), "chrome_profile")
        ),
        linkedin_base_url="https://www.linkedin.com/",
        linkedin_feed_url="https://www.linkedin.com/feed/",
        linkedin_login_url="https://www.linkedin.com/login/",
        min_typing_delay=_safe_float(source.get("MIN_TYPING_DELAY"), 0.05),
        max_typing_delay=_safe_float(source.get("MAX_TYPING_DELAY"), 0.15),
        min_action_delay=_safe_int(source.get("MIN_ACTION_DELAY"), 1),
        max_action_delay=_safe_int(source.get("MAX_ACTION_DELAY"), 3),
        min_page_load_delay=_safe_int(source.get("MIN_PAGE_LOAD_DELAY"), 2),
        max_page_load_delay=_safe_int(source.get("MAX_PAGE_LOAD_DELAY"), 5),
        element_timeout=_safe_int(source.get("ELEMENT_TIMEOUT"), 10),
        short_timeout=_safe_int(source.get("SHORT_TIMEOUT"), 5),
        default_topic_file="Topics.txt",
        log_directory=log_directory,
        custom_posts_file=source.get("CUSTOM_POSTS_FILE", "CustomPosts.txt"),
        max_post_length=1300,
        enable_text_preprocessing=_safe_bool(
            source.get("ENABLE_TEXT_PREPROCESSING"), False
        ),
        summarize_input=_safe_bool(source.get("SUMMARIZE_INPUT"), False),
        summarize_ratio=_safe_float(source.get("SUMMARIZE_RATIO"), 0.3),
        max_input_chars=_safe_int(source.get("MAX_INPUT_CHARS"), 3200),
        capture_typeahead_html=_safe_bool(
            source.get("CAPTURE_TYPEAHEAD_HTML"), False
        ),
        typeahead_capture_dir=source.get(
            "TYPEAHEAD_CAPTURE_DIR", str(pathlib.Path(log_directory) / "typeahead")
        ),
    )


CONFIG = load_config()
