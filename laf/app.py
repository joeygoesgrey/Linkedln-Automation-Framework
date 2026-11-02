"""Application wiring and the thin LinkedIn bot orchestrator.

WHY
  One function builds the driver, the AI helpers and every service, so callers
  never wire the graph twice and no module global changes at runtime.
"""

import json
import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver

from laf.ai.client import ContentCalendarRequest, OpenAIClient
from laf.ai.content import ContentGenerator
from laf.browser.driver import DriverFactory
from laf.config import Config, load_config
from laf.errors import AiError, LAFError
from laf.flows.pursue import PursueFlow
from laf.messages import render
from laf.models import CalendarModel, TopicsModel
from laf.services.composer import ComposerService
from laf.services.engage import EngageService
from laf.services.engage_dom import EngageDomService
from laf.services.feed_actions import FeedService
from laf.services.login import LoginService
from laf.services.media import MediaService
from laf.services.mentions import MentionService
from laf.services.overlays import OverlayService
from laf.services.post_extractor import PostExtractor
from laf.services.profile_actions import ProfileService
from laf.services.verify import VerifyService
from laf.text import preprocess_for_ai
from laf.ui import UiActions

logger = logging.getLogger(__name__)


@dataclass
class Services:
    """Every LinkedIn service, wired once and shared by the bot.

    WHY
      Grouping the services in one typed object lets the bot reach a service by
      name instead of carrying a dozen attributes.
    """

    ui: UiActions
    overlays: OverlayService
    verify: VerifyService
    mentions: MentionService
    engage_dom: EngageDomService
    media: MediaService
    login: LoginService
    composer: ComposerService
    feed: FeedService
    profile: ProfileService
    engage: EngageService


@dataclass
class App:
    """The built application graph.

    WHY
      Hold the settings, the driver, the services and the AI helpers so
      :class:`LinkedInBot` only needs this one object.
    """

    config: Config
    driver: WebDriver
    services: Services
    openai_client: Optional[OpenAIClient]
    content_generator: ContentGenerator
    post_extractor: PostExtractor


def build_app(
    config: Config | None = None,
    use_openai: bool = True,
    headless_override: bool | None = None,
    driver: WebDriver | None = None,
) -> App:
    """Build the driver, the AI helpers and every service in one place.

    WHY
        One function must own the wiring so no module global is mutated after
        startup, and so tests can swap the driver and skip the browser.

    Args
        config: Config | None, the settings to use; defaults to
            ``load_config(headless_override=headless_override)``. When config is
            given, headless_override is ignored.
        use_openai: bool, whether the AI client may be built.
        headless_override: bool | None, the headless flag for ``load_config``;
            ignored when config is supplied. None leaves the environment value
            alone.
        driver: WebDriver | None, a driver for tests; when given the driver
            factory is not called, but every service is still built around it.

    Returns
        App: the built settings, driver, services and AI helpers.

    Raises
        DriverError: when no driver is given and no Chrome or driver can be
            started.
    """

    resolved_config = (
        config
        if config is not None
        else load_config(headless_override=headless_override)
    )

    if driver is None:
        driver = DriverFactory.setup_driver(resolved_config)

    ui = UiActions(driver, resolved_config)
    overlays = OverlayService(ui)
    verify = VerifyService(ui)
    mentions = MentionService(ui, overlays)
    engage_dom = EngageDomService(ui, overlays, mentions)
    media = MediaService(ui, overlays)
    login = LoginService(ui, resolved_config)
    composer = ComposerService(
        ui,
        resolved_config,
        overlays,
        media,
        mentions,
        verify,
    )
    feed = FeedService(ui, resolved_config, overlays, mentions, engage_dom)
    profile = ProfileService(ui, resolved_config, engage_dom)
    engage = EngageService(ui, resolved_config, engage_dom, overlays, mentions)

    services = Services(
        ui=ui,
        overlays=overlays,
        verify=verify,
        mentions=mentions,
        engage_dom=engage_dom,
        media=media,
        login=login,
        composer=composer,
        feed=feed,
        profile=profile,
        engage=engage,
    )

    openai_client = (
        OpenAIClient(config=resolved_config)
        if (use_openai and resolved_config.openai_api_key)
        else None
    )

    return App(
        config=resolved_config,
        driver=driver,
        services=services,
        openai_client=openai_client,
        content_generator=ContentGenerator(
            ai_client=openai_client, config=resolved_config
        ),
        post_extractor=PostExtractor(driver, resolved_config),
    )


class LinkedInBot:
    """Thin orchestrator that drives LinkedIn automation flows.

    WHY
      Give callers one workflow object while the actual work lives in the
      services built by :func:`build_app`. The bot does not log in on
      construction; each flow that needs a session calls login itself.
    """

    def __init__(self, app: App) -> None:
        """Store the built app without touching the network.

        WHY
            Constructing the bot must not start a session, so callers decide
            when to log in and tests can build it cheaply.

        Args
            app: App, the graph returned by :func:`build_app`.

        MUTATIONS
            stores the App on the instance.
        """
        self.app = app

    def process_topics(
        self,
        topic_file_path: Optional[str] = None,
        image_directory: Optional[str] = None,
        schedule_date: Optional[str] = None,
        schedule_time: Optional[str] = None,
        engage_with_feed: bool = False,
        max_posts_to_engage: int = 3,
        perspectives: Optional[List[str]] = None,
        no_images: bool = False,
    ) -> Dict[str, Any]:
        """Publish a post sourced from a topics file and optionally engage feed posts.

        WHY
          Automate daily posting from a backlog of ideas and add lightweight
          engagement to boost reach.

        Args
          topic_file_path: Optional[str], a newline-delimited topic file from
            the caller, or None to use the configured default.
          image_directory: Optional[str], the folder to sample images from.
          schedule_date: Optional[str], the date to schedule the post.
          schedule_time: Optional[str], the time to schedule the post.
          engage_with_feed: bool, whether to run the feed engagement stream.
          max_posts_to_engage: int, the most feed posts to touch.
          perspectives: Optional[List[str]], the AI comment perspectives.
          no_images: bool, whether to skip image uploads.

        Returns
          Dict[str, Any], posting success, post url, engagement result and the
          perspectives used.

        Raises
          pydantic.ValidationError: when a TopicsModel field is invalid; the
            body re-raises it.

        MUTATIONS
          writes the topics file and its posted history when the post succeeds.
        """
        config = self.app.config
        try:
            validated = TopicsModel(
                topic_file_path=topic_file_path or config.default_topic_file,
                image_directory=image_directory,
                schedule_date=schedule_date,
                schedule_time=schedule_time,
                engage_with_feed=engage_with_feed,
                max_posts_to_engage=max_posts_to_engage,
                perspectives=perspectives,
                no_images=no_images,
            )
        except ValidationError as e:
            logger.error(f"Validation failed for process_topics: {e}")
            raise

        topic_file_path = validated.topic_file_path
        perspectives = validated.perspectives or ["auto"]

        results: Dict[str, Any] = {
            "post_created": False,
            "post_url": None,
            "engagement": None,
            "perspectives_used": [],
        }

        logger.info(f"Processing topics from {topic_file_path}")

        try:
            topics: List[str] = []
            topics_file_exists = False

            if topic_file_path and Path(topic_file_path).exists():
                topics_file_exists = True
                with open(topic_file_path, "r") as f:
                    topics = [t.strip() for t in f.readlines() if t.strip()]

            if topics:
                chosen_topic = random.choice(topics)
                logger.info(f"Found {len(topics)} topics. Selected: {chosen_topic}")
            else:
                default_topics = getattr(
                    self.app.content_generator,
                    "_default_posts",
                    {
                        "leadership",
                        "productivity",
                        "technology",
                        "networking",
                        "remote work",
                        "iot",
                        "ai",
                        "blockchain",
                    },
                )
                chosen_topic = random.choice(list(default_topics))
                logger.info(f"No topics file found. Using built-in topic: {chosen_topic}")

            post_content = self.app.content_generator.generate_post_content(chosen_topic)

            if config.enable_text_preprocessing:
                post_content = preprocess_for_ai(
                    post_content,
                    summarize_ratio=config.summarize_ratio if config.summarize_input else None,
                    max_chars=config.max_input_chars,
                )

            images_to_post = []
            if not no_images:
                images_to_post = self._select_images(image_directory)

            if self.app.services.login.login():
                post_success = True
                try:
                    self.app.services.composer.post_to_linkedin(
                        post_content,
                        image_paths=images_to_post,
                        schedule_date=schedule_date,
                        schedule_time=schedule_time,
                    )
                except LAFError as error:
                    message, hint = render(error)
                    logger.error("%s %s [%s]", message, hint, error.code)
                    post_success = False
                results["post_created"] = post_success

                if post_success and engage_with_feed:
                    logger.info("Post successful. Engaging with feed...")
                    try:
                        engagement_ok = self.app.services.engage.engage_stream(
                            mode="comment",
                            comment_text=json.dumps(
                                {
                                    "perspectives": perspectives,
                                    "max_tokens": 150,
                                    "temperature": 0.7,
                                }
                            ),
                            max_actions=max_posts_to_engage,
                            include_promoted=False,
                        )
                        results["engagement"] = {"success": bool(engagement_ok)}
                    except (WebDriverException, LAFError) as e:
                        logger.error(f"Error engaging with feed: {e}")
                        results["engagement"] = {"success": False, "error": str(e)}

                if post_success and topics_file_exists and chosen_topic in topics:
                    self._update_topics_file(topic_file_path, topics, chosen_topic)

            time.sleep(random.uniform(5, 10))

        except (LAFError, WebDriverException, OSError, ValueError):
            logger.error("An error occurred while processing topics.", exc_info=True)

        return results

    def post_custom_text(
        self,
        post_text: str,
        image_directory: Optional[str] = None,
        mention_anchors: Optional[List[str]] = None,
        mention_names: Optional[List[str]] = None,
        image_paths: Optional[List[str]] = None,
        schedule_date: Optional[str] = None,
        schedule_time: Optional[str] = None,
        no_images: bool = False,
    ) -> bool:
        """Publish a caller-supplied post with optional media and mentions.

        WHY
          Support ad-hoc posts outside the topic workflow while reusing the
          same resilient Selenium interactions.

        Args
          post_text: str, the content to publish, from the caller.
          image_directory: Optional[str], the folder to sample images from when
            image_paths is empty.
          mention_anchors: Optional[List[str]], text anchors before a mention.
          mention_names: Optional[List[str]], display names for the anchors.
          image_paths: Optional[List[str]], explicit image files to attach.
          schedule_date: Optional[str], the date to schedule the post.
          schedule_time: Optional[str], the time to schedule the post.
          no_images: bool, whether to skip image uploads.

        Returns
          bool, True on apparent success, False otherwise.

        Raises
          TypeError: when no_images is not a bool.
        """
        if not isinstance(post_text, str) or not post_text.strip():
            logger.error("post_custom_text requires a non-empty post_text string")
            return False
        if not isinstance(no_images, bool):
            raise TypeError(f"no_images must be a bool, got {type(no_images)}")

        try:
            processed_text = self._apply_anchor_mentions(post_text, mention_anchors, mention_names)

            images_to_post = []
            if not no_images:
                images_to_post = [
                    str(Path(p).absolute()) for p in (image_paths or []) if Path(p).exists()
                ]
                if not images_to_post:
                    images_to_post = self._select_images(image_directory)

            if not self.app.services.login.login():
                logger.error("Login failed before custom post")
                return False

            try:
                self.app.services.composer.post_to_linkedin(
                    processed_text,
                    image_paths=images_to_post,
                    schedule_date=schedule_date,
                    schedule_time=schedule_time,
                )
            except LAFError as error:
                message, hint = render(error)
                logger.error("%s %s [%s]", message, hint, error.code)
                return False
            logger.info("Successfully posted custom text")
            return True

        except (LAFError, WebDriverException, OSError):
            logger.error("An error occurred in post_custom_text.", exc_info=True)
            return False

    def _apply_anchor_mentions(
        self, post_text: str, anchors: Optional[List[str]], names: Optional[List[str]]
    ) -> str:
        """Inject ``@{Name}`` tokens after configured anchor phrases.

        WHY
          Let users say where mentions belong without crafting placeholders by
          hand, and leave the text unchanged when the inputs do not line up.

        Args
          post_text: str, the original post text from the caller.
          anchors: Optional[List[str]], the anchor phrases from the caller.
          names: Optional[List[str]], the display names for each anchor.

        Returns
          str, the post text with inline mention placeholders, or the original
          text when the pairs are empty or uneven.
        """
        try:
            if not anchors or not names or len(anchors) != len(names):
                return post_text

            result = post_text
            for anchor, name in zip(anchors, names):
                if not anchor or not name:
                    continue
                words = str(anchor).strip().split()
                if not words:
                    continue

                pattern = r"\b" + r"\s+".join(map(re.escape, words)) + r"\b"
                replacement = r"\g<0> @{" + name + r"}"

                try:
                    result, n = re.subn(pattern, replacement, result, count=1, flags=re.IGNORECASE)
                    if n == 0:
                        logger.info(f"Anchor not found: '{anchor}'")
                except re.error as re_err:
                    logger.info(f"Anchor substitution failed for '{anchor}': {re_err}")
            return result
        except (TypeError, re.error) as e:
            logger.info(f"_apply_anchor_mentions failed; returning original text: {e}")
            return post_text

    def _select_images(self, image_directory: Optional[str]) -> List[str]:
        """Pick up to three random images from a directory.

        WHY
          Add media variety to posts without repetitive manual selection, and
          return an empty list when the folder is missing or empty.

        Args
          image_directory: Optional[str], the folder to scan, from the caller.

        Returns
          List[str], image paths for upload, or an empty list.
        """
        if not image_directory:
            return []

        try:
            image_dir = Path(image_directory)
            if not image_dir.exists() or not image_dir.is_dir():
                logger.warning(f"Image directory does not exist: {image_directory}")
                return []

            image_files = [
                str(f)
                for f in image_dir.glob("*")
                if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif")
            ]

            if image_files:
                return random.sample(image_files, min(3, len(image_files)))

            logger.info("No images found in directory")
            return []
        except OSError as e:
            logger.error(f"Error selecting images: {e}")
            return []

    def _update_topics_file(self, file_path: str, topics: List[str], posted_topic: str) -> None:
        """Persist topic progress by removing the used idea and logging history.

        WHY
          Prevent reposting the same topic and keep an audit trail of what went
          live and when.

        Args
          file_path: str, the topics file path from the caller.
          topics: List[str], the remaining topics; the posted one is removed.
          posted_topic: str, the topic that was just published.

        MUTATIONS
          removes the posted topic from the topics list, rewrites the topics
          file and appends one line to the posted history file.
        """
        try:
            topics.remove(posted_topic)
            path = Path(file_path)
            path.write_text("\n".join(topics) + ("\n" if topics else ""), encoding="utf-8")
            logger.info(f"Updated topics file. {len(topics)} topics remaining.")

            stem = path.stem or "topics"
            suffix = path.suffix or ".txt"
            history_path = path.with_name(f"{stem}_posted{suffix}")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with history_path.open("a", encoding="utf-8") as history_file:
                history_file.write(f"{timestamp} | {posted_topic}\n")
            logger.info("Recorded posted topic in %s", history_path)
        except ValueError:
            logger.warning("Posted topic '%s' not found in %s", posted_topic, file_path)
        except OSError as e:
            logger.error(f"Error updating topics file: {e}")

    def generate_content_calendar(
        self, niche: str, output_file: str = "calendar.txt", total_posts: int = 30
    ) -> bool:
        """Produce a multi-day content plan using OpenAI and save to disk.

        WHY
            Turn one niche into a dated posting plan, and report a clean False
            instead of a crash when the AI client was never built.

        Args
            niche: str, the industry or topic niche.
            output_file: str, path to save the generated calendar.
            total_posts: int, number of post ideas to generate.

        Returns
            bool, True when generation and saving succeeded, False when the AI
            client is missing or the call failed.

        Raises
          pydantic.ValidationError: when a CalendarModel field is invalid; the
            body re-raises it.
        """
        try:
            validated = CalendarModel(niche=niche, output_file=output_file, total_posts=total_posts)
        except ValidationError as e:
            logger.error(f"Validation failed for generate_content_calendar: {e}")
            raise

        if not self.app.openai_client:
            logger.error("OpenAI client not initialized. Cannot generate calendar.")
            return False

        logger.info(
            f"Generating {validated.total_posts}-day content calendar for niche: {validated.niche}"
        )

        request = ContentCalendarRequest(
            niche=validated.niche,
            goal="Establish thought leadership and build community",
            audience="Professionals, enthusiasts, and potential collaborators",
            tone="Informative, engaging, and authentic",
            content_types=["text", "images", "personal stories", "industry news"],
            frequency="Daily",
            total_posts=validated.total_posts,
            hashtags=[validated.niche.replace(" ", ""), "Growth", "Networking", "Tech"],
        )

        try:
            calendar_text = self.app.openai_client.generate_content_calendar(request)

            with open(validated.output_file, "w", encoding="utf-8") as f:
                f.write(calendar_text)

            logger.info(f"Successfully generated calendar and saved to {validated.output_file}")
            return True
        except (AiError, OSError) as e:
            logger.error(f"Failed to generate or save content calendar: {e}")
            return False

    def close(self) -> None:
        """Terminate the Selenium session and release resources.

        WHY
          Avoid lingering browser processes and free OS resources once work is
          complete, without raising when the driver is already gone.

        MUTATIONS
          ends the Selenium driver session.
        """
        try:
            self.app.driver.quit()
            logger.info("Driver session ended cleanly.")
        except WebDriverException as e:
            logger.error(f"Error closing driver: {e.msg}")

    def pursue_investor(
        self,
        profile_name: str,
        max_posts: int = 5,
        should_follow: bool = True,
        should_like: bool = True,
        should_comment: bool = True,
        comment_perspectives: Optional[List[str]] = None,
        bio_keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Pursue and engage with a specific person's profile.

        WHY
            Run the profile engagement flow and always return a results dict,
            even when login, search or a single action fails.

        Args
            profile_name: str, the person's name.
            max_posts: int, maximum posts to engage with.
            should_follow: bool, whether to follow the profile.
            should_like: bool, whether to like posts.
            should_comment: bool, whether to comment on posts.
            comment_perspectives: list[str] | None, perspectives for AI comments.
            bio_keywords: list[str] | None, words to match in the profile bio.

        Returns
            dict: the profile name plus followed, counts and any errors.

        Raises
          pydantic.ValidationError: when a PursueModel field is invalid.
          ProfileError: when no profile matches the name.
        """
        flow = PursueFlow(
            services=self.app.services,
            driver=self.app.driver,
            openai_client=self.app.openai_client,
            post_extractor=self.app.post_extractor,
        )
        return flow.run(
            profile_name=profile_name,
            max_posts=max_posts,
            should_follow=should_follow,
            should_like=should_like,
            should_comment=should_comment,
            comment_perspectives=comment_perspectives,
            bio_keywords=bio_keywords,
        )
