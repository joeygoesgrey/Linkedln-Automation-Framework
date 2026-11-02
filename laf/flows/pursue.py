"""Pursue one profile: log in, find it, follow it and engage its posts.

WHY
  The bot class must stay a thin delegate, so this module owns the order of the
  pursue steps and the results dict that the command line prints.
"""

import logging
import time
from typing import Any, Callable, Dict, List, Literal, Optional, Protocol, cast

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver

from laf.ai.client import OpenAIClient
from laf.errors import AiError, ProfileError
from laf.models import PursueModel
from laf.services.engage_utils import choose_ai_perspective, normalize_perspectives
from laf.services.login import LoginService
from laf.services.post_extractor import PostExtractor
from laf.services.profile_actions import ProfileService

logger = logging.getLogger(__name__)

Perspective = Literal["auto", "motivational", "thoughtful", "reality_check"]

FALLBACK_COMMENT = "Great post! Thanks for sharing."

LOGIN_FAILED_MESSAGE = "Aborting pursue_investor: Failed to login to LinkedIn."


class _Services(Protocol):
    """The two services the pursue flow calls.

    WHY
      The concrete Services dataclass lives in laf.app, and importing it here
      would make a cycle, so this module names only the members it uses.
    """

    login: LoginService
    profile: ProfileService


def _get_random_perspective(perspectives: List[str]) -> Perspective:
    """Select a perspective token for AI comment generation.

    WHY
        The AI comment call accepts only the four perspective values, so the
        shared rules drop unknown words and map the old alias before the call.

    Args
        perspectives: list[str], candidate labels from the caller.

    Returns
        Perspective: auto, motivational, thoughtful or reality_check.
    """
    return cast(Perspective, choose_ai_perspective(normalize_perspectives(perspectives)))


class PursueFlow:
    """Run the profile pursuit workflow and return its results dict.

    WHY
      Give the bot one object that owns the login, search, follow and engagement
      order, so a failure in one step cannot silently reorder the others.
    """

    def __init__(
        self,
        services: _Services,
        driver: WebDriver,
        openai_client: Optional[OpenAIClient],
        post_extractor: PostExtractor,
    ) -> None:
        """Store the parts the flow needs without touching the network.

        WHY
            Keep construction free of browser work so tests can build the flow
            with fakes and the caller decides when a run starts.

        Args
            services: _Services, the logged in session and profile actions from
                :func:`laf.app.build_app`.
            driver: WebDriver, the browser used to open the found profile.
            openai_client: Optional[OpenAIClient], the AI writer, or None when
                the AI was disabled.
            post_extractor: PostExtractor, reads the text of one post for the
                AI writer.

        MUTATIONS
            stores the services, the driver, the AI client and the extractor on
            the instance.
        """
        self.services = services
        self.driver = driver
        self.openai_client = openai_client
        self.post_extractor = post_extractor

    def run(
        self,
        profile_name: str,
        max_posts: int = 5,
        should_follow: bool = True,
        should_like: bool = True,
        should_comment: bool = True,
        comment_perspectives: Optional[List[str]] = None,
        bio_keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Pursue one profile and return the same results dict as the bot did.

        WHY
            Keep the command line contract stable while the steps move out of
            the bot class, including the error list when login fails.

        Args
            profile_name: str, the person's name from the caller.
            max_posts: int, the most posts to engage.
            should_follow: bool, whether to follow the profile.
            should_like: bool, whether to like posts.
            should_comment: bool, whether to comment on posts.
            comment_perspectives: Optional[List[str]], AI comment angles from the
                caller, or None for the defaults.
            bio_keywords: Optional[List[str]], words to match in the search
                result text, or None to search without the filter.

        Returns
            Dict[str, Any], the profile name plus followed, the three counts and
            the errors list.

        Raises
            pydantic.ValidationError: when a PursueModel field is invalid.
            ProfileError: when no profile matches the name.
        """
        validated = self._validate(
            profile_name=profile_name,
            max_posts=max_posts,
            should_follow=should_follow,
            should_like=should_like,
            should_comment=should_comment,
            comment_perspectives=comment_perspectives,
            bio_keywords=bio_keywords,
        )

        results: Dict[str, Any] = {
            "profile": validated.profile_name,
            "followed": False,
            "posts_engaged": 0,
            "likes_given": 0,
            "comments_made": 0,
            "errors": [],
        }

        profile_url = self._find_profile(validated)
        if profile_url is None:
            logger.error(LOGIN_FAILED_MESSAGE)
            results["errors"].append(LOGIN_FAILED_MESSAGE)
            return results

        logger.info(f"Navigating to profile: {profile_url}")
        self.driver.get(profile_url)
        time.sleep(3)

        if validated.should_follow:
            results["followed"] = self._follow_profile(validated, results["errors"])

        logger.info(
            f"Opening profile posts view and engaging up to {validated.max_posts} posts"
        )
        if not self.services.profile.open_profile_posts_view():
            logger.warning(
                "Could not confirm profile posts view; continuing with current page"
            )

        generator = (
            self._build_comment_generator(validated)
            if validated.should_comment
            else None
        )
        engagement = self._engage(validated, generator)

        results["posts_engaged"] = engagement.get("posts_engaged", 0)
        results["likes_given"] = engagement.get("likes", 0)
        results["comments_made"] = engagement.get("comments", 0)

        logger.info(
            f"Engagement summary for {validated.profile_name}: "
            f"actions={results['posts_engaged']}, skipped={engagement.get('skipped', 0)}"
        )
        return results

    def _validate(
        self,
        profile_name: str,
        max_posts: int,
        should_follow: bool,
        should_like: bool,
        should_comment: bool,
        comment_perspectives: Optional[List[str]],
        bio_keywords: Optional[List[str]],
    ) -> PursueModel:
        """Build the typed model from the caller's arguments.

        WHY
            Reject a bad name or limit before any browser step, and let the
            caller's validation error reach main.py unchanged.

        Args
            profile_name: str, the person's name from the caller.
            max_posts: int, the most posts to engage.
            should_follow: bool, whether to follow the profile.
            should_like: bool, whether to like posts.
            should_comment: bool, whether to comment on posts.
            comment_perspectives: Optional[List[str]], AI comment angles.
            bio_keywords: Optional[List[str]], words to match in the bio.

        Returns
            PursueModel, the checked profile name and options.

        Raises
            pydantic.ValidationError: when a field fails a type or range rule.
        """
        return PursueModel(
            profile_name=profile_name,
            max_posts=max_posts,
            should_follow=should_follow,
            should_like=should_like,
            should_comment=should_comment,
            comment_perspectives=comment_perspectives,
            bio_keywords=bio_keywords,
        )

    def _find_profile(self, validated: PursueModel) -> Optional[str]:
        """Log in, search for the profile and return its URL.

        WHY
            A missing profile must stop the run with a named error, while a
            failed login must only report False so the caller can record it.

        Args
            validated: PursueModel, the checked name and bio keywords.

        Returns
            Optional[str], the profile URL, or None when the login call
            returned False.

        Raises
            ProfileError: when the search returns no profile URL.
        """
        if not self.services.login.login():
            return None

        logger.info(f"Searching for profile: {validated.profile_name}")
        if validated.bio_keywords:
            logger.info(
                f"Looking for bio containing: {', '.join(validated.bio_keywords)}"
            )

        profile_url = self.services.profile.search_profile(
            validated.profile_name, bio_keywords=validated.bio_keywords
        )
        if not profile_url:
            raise ProfileError("PROFILE_NOT_FOUND", name=validated.profile_name)

        return profile_url

    def _follow_profile(self, validated: PursueModel, errors: List[Any]) -> bool:
        """Follow the open profile and record a failure instead of raising.

        WHY
            One failed follow must not stop the post engagement that follows, so
            the sentence lands in the results errors list and False comes back.

        Args
            validated: PursueModel, the checked profile name used in logs.
            errors: List[Any], the results error list to append to on failure.

        Returns
            bool, True when the follow click happened, False when it did not or
            the follow call raised.

        MUTATIONS
            appends one sentence to errors when the follow call raises, and logs
            it.
        """
        try:
            if self.services.profile.follow_profile():
                logger.info(f"Successfully followed {validated.profile_name}")
                return True
        except WebDriverException as e:
            error_msg = f"Failed to follow profile: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
        return False

    def _build_comment_generator(
        self, validated: PursueModel
    ) -> Callable[[object], str]:
        """Build the per post comment writer, with a fixed fallback sentence.

        WHY
            One missing AI client or one unreadable post must not stop the run,
            so every failure returns the fallback sentence instead of raising.

        Args
            validated: PursueModel, the checked comment perspectives.

        Returns
            Callable[[object], str], a function that takes one post element and
            returns a comment sentence.
        """

        def build_comment(post_root: object) -> str:
            """Return an AI comment for one post, or the fixed fallback.

            WHY
                Keep profile engagement moving when the AI client is missing or
                extraction or generation fails, so one bad post does not stop
                the batch.

            Args
                post_root: object, the post element handed in by the profile
                    service.

            Returns
                str, the AI comment text or the fixed fallback sentence.
            """
            client = self.openai_client
            if client is not None:
                try:
                    post_text = self.post_extractor.extract_text(post_root)
                except WebDriverException:
                    post_text = ""
                if post_text:
                    try:
                        perspective = _get_random_perspective(
                            validated.comment_perspectives or ["auto"]
                        )
                        comment, _tone = client.generate_comment(
                            post_text=post_text,
                            perspective=perspective,
                            max_tokens=180,
                            temperature=0.7,
                        )
                        return comment
                    except AiError as err:
                        logger.error(f"AI comment generation failed: {err}")
            return FALLBACK_COMMENT

        return build_comment

    def _engage(
        self, validated: PursueModel, generator: Optional[Callable[[object], str]]
    ) -> Dict[str, Any]:
        """Like and comment on the open profile's posts.

        WHY
            Keep the engagement call and its options in one place so the caller
            only reads the counts that the service returns.

        Args
            validated: PursueModel, the checked post limit and action flags.
            generator: Optional[Callable[[object], str]], the comment writer, or
                None when commenting is disabled.

        Returns
            Dict[str, Any], the service counts for posts_engaged, likes,
            comments, reposts and skipped.
        """
        return self.services.profile.engage_profile_posts(
            max_posts=validated.max_posts,
            should_like=validated.should_like,
            should_comment=validated.should_comment,
            comment_generator=generator,
            mention_author=True,
            mention_position="prepend",
        )
