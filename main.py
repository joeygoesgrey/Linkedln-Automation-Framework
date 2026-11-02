#!/usr/bin/env python3
"""LinkedIn bot command-line entry point."""

import json
import logging
import sys

from pydantic import ValidationError
from selenium.common.exceptions import WebDriverException

from laf.app import LinkedInBot, build_app
from laf.cli import setup_argument_parser
from laf.errors import LAFError
from laf.logging_setup import configure_logging
from laf.messages import UNEXPECTED, render
from laf.models import (
    CalendarModel,
    EngageModel,
    PostModel,
    PursueModel,
    RepostModel,
    TopicsModel,
)

logger = logging.getLogger(__name__)


def main() -> int:
    """Run the command named on the command line.

    WHY
        Turn every failure into a plain sentence and a stable exit code, so the
        user never reads a Python trace on screen, whatever the command did.

    Returns
        int, 0 when the command finished, 1 when it failed.

    MUTATIONS
        Sets up global logging and closes the bot in the finally block, when a
        bot was built.
    """
    bot = None
    log_file = None
    try:
        parser = setup_argument_parser()
        args = parser.parse_args()
        log_file = configure_logging(debug=args.debug)

        # The flag can only turn headless on. With no flag, None keeps the
        # value from the environment, which stays the default of true.
        headless_override = True if args.headless else None
        bot = LinkedInBot(
            build_app(use_openai=not args.no_ai, headless_override=headless_override)
        )

        code = _dispatch(bot, args)
        return 0 if code == 0 else _finish_failed(bot, log_file)
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting.")
        return 1
    except ValidationError as error:
        logger.error("%s", _describe_validation(error))
        return _finish_failed(bot, log_file)
    except LAFError as error:
        message, hint = render(error)
        logger.error(
            "%s %s [%s]",
            message,
            hint,
            error.code,
            exc_info=logger.isEnabledFor(logging.DEBUG),
        )
        return _finish_failed(bot, log_file)
    except Exception as error:
        message, hint = UNEXPECTED
        logger.error(
            "%s %s",
            message,
            hint,
            exc_info=logger.isEnabledFor(logging.DEBUG),
        )
        logger.debug("The unexpected error was: %s", error)
        return _finish_failed(bot, log_file)
    finally:
        if bot is not None:
            try:
                bot.close()
            except WebDriverException as close_error:
                logger.debug("Ignoring error while closing the bot: %s", close_error)


def _dispatch(bot: LinkedInBot, args) -> int:
    """Run the command named on the command line.

    WHY
        One lookup keeps main free of the command list, so main only builds the
        bot, reports a failure and closes.

    Args
        bot: LinkedInBot, the built bot that owns every service.
        args: argparse.Namespace, the parsed command line values.

    Returns
        int, the exit code the named command reported, or 1 when no command was
        given.
    """
    if args.command == "post":
        return _run_post(bot, args)
    if args.command == "generate-calendar":
        return _run_calendar(bot, args)
    if args.command == "engage":
        return _run_engage(bot, args)
    if args.command == "pursue":
        return _run_pursue(bot, args)
    if args.command == "repost":
        return _run_repost(bot, args)
    logger.error("No command was given.")
    return 1


def _finish_failed(bot, log_file) -> int:
    """Say where the detail of a failed run lives, then report the failure.

    WHY
        The user needs the log path and how many selectors the last failed
        lookup tried, so they can find the real selector without reading a
        Python trace.

    Args
        bot: Optional[LinkedInBot], the bot main built, or None when the run
            failed before the bot existed.
        log_file: Optional[Path], the file configure_logging opened.

    Returns
        int, always 1, so a failure exit is one line at each call site.

    MUTATIONS
        logs the log path and the last selector miss, which reaches the screen
        and the log file.
    """
    if log_file is not None:
        logger.error("Log file: %s", log_file)
    services = getattr(getattr(bot, "app", None), "services", None)
    miss = getattr(getattr(services, "ui", None), "last_miss", None)
    if miss is not None:
        logger.error(
            "Last selector miss: %s selectors tried on %s",
            len(miss.candidates),
            miss.page,
        )
    return 1


def _describe_validation(error: ValidationError) -> str:
    """Turn a model rejection into one plain sentence for the user.

    WHY
        Pydantic prints a multi line technical report, and the user only needs
        to know which value was wrong and why.

    Args
        error: ValidationError, the model rejection caught by main.

    Returns
        str, one sentence naming every rejected field and its reason.
    """
    problems = []
    for item in error.errors():
        field = ".".join(str(part) for part in item["loc"])
        problems.append(f"{field} ({item['msg']})")
    return "The command values are not valid: " + ", ".join(problems)


def _run_post(bot: LinkedInBot, args) -> int:
    """Validate the post arguments and hand them to the bot.

    WHY
        The post command has two paths, custom text or a topics file, and the
        choice must be made in one small place.

    Args
        bot: LinkedInBot, the built bot that owns every service.
        args: argparse.Namespace, the parsed command line values.

    Returns
        int, 0 when the post work was handed to the bot.

    Raises
        ValidationError: when a value does not fit the PostModel or TopicsModel
        rules.
    """
    if args.text:
        # A direct post has text, so the post model is the right rule set.
        validated = PostModel(
            post_text=args.text,
            image_directory=args.images_dir,
            schedule_date=args.schedule_date,
            schedule_time=args.schedule_time,
            no_images=args.no_images,
        )
        bot.post_custom_text(
            post_text=validated.post_text,
            image_directory=validated.image_directory,
            schedule_date=validated.schedule_date,
            schedule_time=validated.schedule_time,
            no_images=validated.no_images,
        )
        return 0

    # A topics run has no text yet, so the post model would reject it for an
    # empty field that is correct at this point. The topics model fits instead.
    topics = TopicsModel(
        topic_file_path=args.topics_file,
        image_directory=args.images_dir,
        schedule_date=args.schedule_date,
        schedule_time=args.schedule_time,
        no_images=args.no_images,
    )
    bot.process_topics(
        topic_file_path=topics.topic_file_path,
        image_directory=topics.image_directory,
        schedule_date=topics.schedule_date,
        schedule_time=topics.schedule_time,
        no_images=topics.no_images,
    )
    return 0


def _run_calendar(bot: LinkedInBot, args) -> int:
    """Validate the calendar arguments and start the calendar job.

    WHY
        The calendar command must fail on bad values before the AI call starts.

    Args
        bot: LinkedInBot, the built bot.
        args: argparse.Namespace, the parsed command line values.

    Returns
        int, 0 when the calendar job was handed to the bot.

    Raises
        ValidationError: when a value does not fit the CalendarModel rules.
    """
    validated = CalendarModel(
        niche=args.niche, output_file=args.output, total_posts=args.total_posts
    )
    bot.generate_content_calendar(
        niche=validated.niche,
        output_file=validated.output_file,
        total_posts=validated.total_posts,
    )
    return 0


def _run_engage(bot: LinkedInBot, args) -> int:
    """Validate the engage arguments and run the feed engagement.

    WHY
        Engagement must log in first and report a clear result instead of a
        silent crash on an empty feed.

    Args
        bot: LinkedInBot, the built bot.
        args: argparse.Namespace, the parsed command line values.

    Returns
        int, 0 when the stream finished, 1 when the login or the stream failed.

    Raises
        ValidationError: when a value does not fit the EngageModel rules.
    """
    validated = EngageModel(mode=args.action, max_actions=args.max_actions)
    if not bot.app.services.login.login():
        logger.error("The login to LinkedIn did not finish.")
        return 1
    success = bot.app.services.engage.engage_stream(
        mode=validated.mode,
        max_actions=validated.max_actions,
        ai_client=bot.app.openai_client,
        post_extractor=bot.app.post_extractor,
    )
    logger.info("Engagement stream finished: %s", "success" if success else "failed")
    return 0 if success else 1


def _run_pursue(bot: LinkedInBot, args) -> int:
    """Validate the pursue arguments and run the profile engagement.

    WHY
        The pursue command returns per post results, and the exit code must show
        whether any of those results carried an error.

    Args
        bot: LinkedInBot, the built bot.
        args: argparse.Namespace, the parsed command line values.

    Returns
        int, 0 when no result carried an error, 1 otherwise.

    Raises
        ValidationError: when a value does not fit the PursueModel rules.
    """
    validated = PursueModel(
        profile_name=args.profile_name,
        max_posts=args.max_posts,
        should_follow=args.should_follow,
        should_like=args.should_like,
        should_comment=args.should_comment,
        comment_perspectives=args.perspectives,
        bio_keywords=args.bio_keywords,
    )
    results = bot.pursue_investor(
        profile_name=validated.profile_name,
        max_posts=validated.max_posts,
        should_follow=validated.should_follow,
        should_like=validated.should_like,
        should_comment=validated.should_comment,
        comment_perspectives=validated.comment_perspectives,
        bio_keywords=validated.bio_keywords,
    )
    logger.info("Pursuit results: %s", json.dumps(results, indent=2))
    return 0 if not results.get("errors") else 1


def _run_repost(bot: LinkedInBot, args) -> int:
    """Validate the repost arguments and repost the first feed post.

    WHY
        Repost has an optional AI writer, and it must be wired here so the
        service stays free of command line and model setup.

    Args
        bot: LinkedInBot, the built bot.
        args: argparse.Namespace, the parsed command line values.

    Returns
        int, 0 when the repost worked, 1 when the login or the repost failed.

    Raises
        ValidationError: when a value does not fit the RepostModel rules.
    """
    validated = RepostModel(
        thoughts_text=args.thoughts,
        mention_author=args.mention_author,
        mention_position=args.mention_position,
    )
    if not bot.app.services.login.login():
        logger.error("The login to LinkedIn did not finish.")
        return 1

    comment_generator = None
    if not validated.thoughts_text and not args.no_ai:
        comment_generator = _build_repost_thoughts(bot)

    success = bot.app.services.feed.repost_first_post(
        thoughts_text=validated.thoughts_text,
        comment_generator=comment_generator,
        mention_author=validated.mention_author,
        mention_position=validated.mention_position,
    )
    if success:
        logger.info("Reposted the first post on the feed.")
        return 0
    logger.error("The repost of the first post did not finish.")
    return 1


def _build_repost_thoughts(bot: LinkedInBot):
    """Build the callable that writes the repost thoughts with AI.

    WHY
        The repost service needs text, not a model client, so this adapter keeps
        the AI call out of the browser code and gives a plain fallback.

    Args
        bot: LinkedInBot, the built bot that owns the AI client and the post
        extractor.

    Returns
        Callable, the nested function that turns one post element into thoughts
        text.
    """

    def build_repost_thoughts(post_root) -> str:
        """Write thoughts for one post, with a fixed fallback.

        WHY
            A failed AI call must not block the repost, so the user still gets
            a usable sentence.

        Args
            post_root: object, the feed post element being reposted.

        Returns
            str, the thoughts text, or the fixed fallback when the AI call
            cannot be made.
        """
        fallback = "Great insights! Had to share this."
        if bot.app.openai_client is None:
            return fallback
        try:
            post_text = bot.app.post_extractor.extract_text(post_root)
        except LAFError as error:
            logger.debug("Could not read the post text for the repost: %s", error.code)
            return fallback
        if not post_text:
            return fallback
        try:
            comment, _tone = bot.app.openai_client.generate_comment(
                post_text=post_text,
                perspective="thoughtful",
                max_tokens=180,
                temperature=0.7,
            )
            return comment
        except LAFError as error:
            logger.warning("The AI writer failed for the repost: %s", error.code)
            return fallback

    return build_repost_thoughts


if __name__ == "__main__":
    sys.exit(main())
