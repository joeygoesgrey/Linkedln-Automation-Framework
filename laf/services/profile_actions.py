"""Search, follow and engage with LinkedIn profiles.

WHY
  Keep every profile action in one service, so a workflow that targets named
  people does not repeat the search and post steps itself.
"""

import logging
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from laf.config import Config
from laf.selectors.engage import EngageSelectors
from laf.selectors.profile import ProfileSelectors

from ..ui import UiActions
from .engage_dom import EngageDomService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PostEngageOptions:
    """The choices one profile engagement pass applies to every post.

    WHY
      Five per run choices would otherwise travel as five separate arguments
      through two methods, and the call site would say nothing about what each
      one means.

    Args
      should_like: bool, True to like each eligible post.
      should_comment: bool, True to comment when a generator returns text.
      comment_generator: Optional[Callable[[Any], Optional[str]]], called with
        one post to produce its comment text, or None.
      mention_author: bool, True to mention the author in the comment.
      mention_position: str, "prepend" or "append" for the mention token.
    """

    should_like: bool
    should_comment: bool
    comment_generator: Optional[Callable[[Any], Optional[str]]]
    mention_author: bool
    mention_position: str


class ProfileService:
    """Find a profile, follow it and engage with its recent posts.

    WHY
      Let a named-person workflow search, follow and react to a profile without
      driving each page itself.
    """

    def __init__(self, ui: UiActions, config: Config, engage_dom: EngageDomService) -> None:
        """
        WHY
          Give profile work the driver, settings and post readers it needs so a
          profile can be found, followed and have its posts engaged.

        Args
          ui: UiActions, the shared Selenium action helper.
          config: Config, the frozen runtime settings.
          engage_dom: EngageDomService, used to read and act on profile posts.

        MUTATIONS
          Stores the driver, settings and the post reader on the instance.
        """
        self.ui = ui
        self.config = config
        self.engage_dom = engage_dom

    def search_profile(
        self, name: str, bio_keywords: Optional[List[str]] = None
    ) -> Optional[str]:
        """Search LinkedIn for a person and return the best profile URL.

        WHY
          Turn a name, and optionally bio keywords, into the URL of the profile
          that a follow or engagement step can use.

        Args
          name: str, the person's name to search for.
          bio_keywords: Optional[List[str]], words to match against the result
            text, or None to take the first result.

        Returns
          Optional[str], the chosen profile URL, or None when no result or no
          profile link was found.

        MUTATIONS
          Navigates the browser, and saves search_error.png when the results
          cannot be read.
        """
        try:
            logger.info(f"Searching for profile: {name}")
            logger.info(
                f"[Stage: Pre-Search] Current browser URL: {self.ui.driver.current_url}"
            )

            # Use direct URL navigation to bypass brittle search UI changes
            encoded_name = urllib.parse.quote(name)
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={encoded_name}"
            self.ui.driver.get(search_url)
            time.sleep(3)

            logger.info(
                f"[Stage: Post-Search Load] Current browser URL: {self.ui.driver.current_url}"
            )

            try:
                profile_elements = WebDriverWait(self.ui.driver, 15).until(
                    EC.presence_of_all_elements_located((By.XPATH, ProfileSelectors.SEARCH_RESULTS))
                )
                logger.info(f"Found {len(profile_elements)} profile elements")

                if not profile_elements:
                    logger.warning("No profile elements found")
                    return None

                if not bio_keywords:
                    for profile in profile_elements:
                        try:
                            link = profile.find_element(By.XPATH, ProfileSelectors.PROFILE_LINK)
                            href = link.get_attribute("href")
                            if href:
                                return href
                        except WebDriverException:
                            continue
                    logger.warning("None of the profile elements contained a valid profile link.")
                    return None

                normalized_keywords = [kw.lower() for kw in bio_keywords if kw]

                for idx, profile in enumerate(profile_elements, 1):
                    try:
                        profile_text = (profile.text or "").lower()
                        logger.debug(f"Profile {idx} text sample: {profile_text[:120]}...")

                        if any(keyword in profile_text for keyword in normalized_keywords):
                            logger.info(
                                "Match found in profile %d based on bio keywords.",
                                idx,
                            )
                            link = profile.find_element(By.XPATH, ProfileSelectors.PROFILE_LINK)
                            return link.get_attribute("href")
                    except WebDriverException as err:
                        logger.debug(f"Error processing profile {idx}: {err.msg}")
                        continue

                logger.info("No matching bio found, returning first valid result")
                for profile in profile_elements:
                    try:
                        link = profile.find_element(By.XPATH, ProfileSelectors.PROFILE_LINK)
                        href = link.get_attribute("href")
                        if href:
                            return href
                    except WebDriverException:
                        continue
                return None

            except WebDriverException as find_err:
                logger.error(f"Error finding profile elements: {find_err.msg}")
                self.ui.driver.save_screenshot("search_error.png")
                logger.info("Screenshot saved as search_error.png")
                return None

        except WebDriverException as e:
            logger.error(f"Error in search_profile: {e.msg}", exc_info=True)
            return None

    def follow_profile(self) -> bool:
        """Follow the open profile unless it is already followed.

        WHY
          Add the profile to the connection list once, and return False instead
          of raising when it is already followed or the button is missing.

        Returns
          bool, True when the follow click was made, False when already
          following or an error occurred.
        """
        try:
            follow_button = WebDriverWait(self.ui.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, ProfileSelectors.FOLLOW_BUTTON))
            )
            if "Following" not in follow_button.text:
                follow_button.click()
                return True
            return False
        except WebDriverException as e:
            logger.error(f"Error following profile: {e.msg}")
            return False

    def open_profile_posts_view(self) -> bool:
        """Open the profile's recent activity view and its Posts tab.

        WHY
          The engagement step needs the profile's post list, so this puts the
          browser on that page and filters out comments and reactions.

        Returns
          bool, True when the activity view was reached, False when navigation
          raised.

        MUTATIONS
          Navigates the browser to the recent activity URL and clicks the Posts
          tab.
        """
        try:
            current_url = self.ui.driver.current_url or ""
            if "recent-activity" not in current_url:
                parsed = urllib.parse.urlparse(current_url)
                base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if not base_url.endswith("/"):
                    base_url += "/"

                recent_activity_url = f"{base_url}recent-activity/all/"
                logger.info(f"Navigating directly to recent activity: {recent_activity_url}")
                self.ui.driver.get(recent_activity_url)
                time.sleep(3)

            # Click the "Posts" tab to filter out comments/reactions
            try:
                posts_tab = WebDriverWait(self.ui.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, ProfileSelectors.POSTS_TAB_BUTTON))
                )
                posts_tab.click()
                time.sleep(2)
                logger.info("Clicked 'Posts' tab in recent activity.")
            except WebDriverException as e:
                logger.warning(
                    "Could not click 'Posts' tab, continuing with current activity view: %s",
                    e.msg if hasattr(e, "msg") else str(e),
                )

            return True
        except WebDriverException as e:
            logger.error(f"Error opening profile posts view: {e.msg}")
            return False

    def _get_profile_post_urls(self, max_posts: int = 5) -> List[str]:
        """Collect URLs of the profile's most recent posts.

        WHY
          Give a caller direct post links without scrolling the whole activity
          page itself.

        Args
          max_posts: int, the most URLs to collect, defaulting to 5.

        Returns
          List[str], the unique post URLs found, up to max_posts, or an empty
          list when navigation or scrolling raised.

        MUTATIONS
          Opens the posts view and scrolls the page to load more posts.
        """
        try:
            self.open_profile_posts_view()

            last_height = self.ui.driver.execute_script("return document.body.scrollHeight")
            post_urls: set[str] = set()

            while len(post_urls) < max_posts:
                posts = self.ui.driver.find_elements(By.CSS_SELECTOR, ProfileSelectors.POST_LINKS)

                for post in posts:
                    href = post.get_attribute("href")
                    if href and "/posts/" in href and href not in post_urls:
                        post_urls.add(href)
                        if len(post_urls) >= max_posts:
                            break

                self.ui.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                time.sleep(2)

                new_height = self.ui.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    try:
                        self.ui.driver.execute_script(
                            "window.scrollTo(0, Math.max(document.body.scrollHeight "
                            "- window.innerHeight, 0));"
                        )
                    except WebDriverException:
                        pass
                    time.sleep(1.5)
                    new_height = self.ui.driver.execute_script(
                        "return document.body.scrollHeight"
                    )
                    if new_height == last_height:
                        break
                last_height = new_height

            return list(post_urls)[:max_posts]

        except WebDriverException as e:
            logger.error(f"Error getting profile posts: {e.msg}")
            return []

    def engage_profile_posts(
        self,
        max_posts: int,
        should_like: bool = True,
        should_comment: bool = True,
        comment_generator: Optional[Callable[[Any], Optional[str]]] = None,
        mention_author: bool = True,
        mention_position: str = "prepend",
    ) -> Dict[str, Any]:
        """Like and comment on a profile's posts up to a limit.

        WHY
          Run profile engagement without re-engaging posts already handled in
          an earlier run, and return a per-action count for the caller.

        Args
          max_posts: int, the most posts to engage in this run.
          should_like: bool, True to like each eligible post.
          should_comment: bool, True to comment when a generator returns text.
          comment_generator: Optional[Callable[[Any], Optional[str]]], called
            with each post to produce comment text, or None.
          mention_author: bool, True to mention the author in the comment.
          mention_position: str, "prepend" or "append" for the mention token.

        Returns
          Dict[str, Any], counts for posts_engaged, likes, comments, reposts and
          skipped, plus an errors list.

        MUTATIONS
          Likes, comments and scrolls the page, and saves the shared engage
          state after each acted-on post.
        """
        results: Dict[str, Any] = {
            "posts_engaged": 0,
            "likes": 0,
            "comments": 0,
            "reposts": 0,
            "skipped": 0,
            "errors": [],
        }

        if max_posts <= 0:
            return results

        engage_state = self._load_engage_lists()
        seen_keys: Set[str] = set()
        stalled = 0
        options = PostEngageOptions(
            should_like=should_like,
            should_comment=should_comment,
            comment_generator=comment_generator,
            mention_author=mention_author,
            mention_position=mention_position,
        )

        while results["posts_engaged"] < max_posts and stalled < 8:
            posts = self._find_profile_posts(results)

            if not posts:
                stalled += 1
                self._wait_for_new_posts()
                continue

            progress = False

            for post in posts:
                if results["posts_engaged"] >= max_posts:
                    break

                outcome = self._handle_one_profile_post(
                    post,
                    engage_state,
                    seen_keys,
                    options,
                    max_posts - results["posts_engaged"],
                )
                results["likes"] += outcome["likes"]
                results["comments"] += outcome["comments"]
                results["errors"].extend(outcome["errors"])
                if outcome["engaged"]:
                    progress = True
                    results["posts_engaged"] += 1
                    try:
                        self.engage_dom.save_engage_state(engage_state)
                    except OSError:
                        pass
                    time.sleep(1.0)
                elif outcome["skipped"]:
                    results["skipped"] += 1

            if progress:
                stalled = 0
            else:
                stalled += 1
                self._wait_for_new_posts()

        return results

    def _load_engage_lists(self) -> Dict[str, List[str]]:
        """Load the liked, commented and reposted lists from the saved state.

        WHY
          Engagement must not repeat a post handled in an earlier run, so the
          saved lists are read once and any wrong shape is reset to empty.

        Returns
          Dict[str, List[str]], the three state lists, each an empty list when
          the saved file held a list or a wrongly typed value.

        MUTATIONS
          Reads the saved state file through the post reader.
        """
        try:
            engage_state = self.engage_dom.load_engage_state()
            if not isinstance(engage_state.get("liked"), list):
                engage_state["liked"] = []
            if not isinstance(engage_state.get("commented"), list):
                engage_state["commented"] = []
            if not isinstance(engage_state.get("reposted"), list):
                engage_state["reposted"] = []
            return engage_state
        except AttributeError:
            return {"liked": [], "commented": [], "reposted": []}

    def _find_profile_posts(
        self, results: Dict[str, Any], limit: int = 12
    ) -> List[Any]:
        """Return the visible posts, recording a lookup failure.

        WHY
          One failed lookup must not end the run, so the browser error is
          logged and added to the results and the caller sees an empty list.

        Args
          results: Dict[str, Any], the run counts and the errors list to append
            to.
          limit: int, the most posts to collect, defaulting to 12.

        Returns
          List[Any], the visible post elements, or an empty list when the
          lookup raised a browser error.
        """
        try:
            return self.engage_dom.find_visible_posts(limit=limit)
        except WebDriverException as err:
            logger.error(f"Error locating profile posts: {err.msg}")
            results["errors"].append(f"Locate posts failed: {err.msg}")
            return []

    def _wait_for_new_posts(self) -> None:
        """Scroll the feed and pause so the next pass can find new posts.

        WHY
          A pass with no progress needs the page to move before it tries again,
          otherwise it reads the same posts and never advances.

        MUTATIONS
          Scrolls the feed through the post reader, or the page directly when
          that raises, then waits.
        """
        try:
            self.engage_dom.scroll_feed(0.8, 1.6)
        except WebDriverException:
            self.ui.driver.execute_script(
                "window.scrollBy(0, window.innerHeight * 0.9);"
            )
        time.sleep(1.2)

    def _profile_post_key(self, post: Any, seen_keys: Set[str]) -> Optional[str]:
        """Return the post's dedupe key, or None when this pass saw it before.

        WHY
          The same post appears on every scroll pass, so a key seen already in
          this run is ignored instead of being liked or counted twice.

        Args
          post: Any, the post element from the visible list.
          seen_keys: Set[str], the keys already handled in this run.

        Returns
          Optional[str], the new key, or None when the key was already seen.

        MUTATIONS
          Adds the new key to seen_keys.
        """
        try:
            urn = self.engage_dom.extract_post_urn(post)
            key = self.engage_dom.post_dedupe_key(post, urn)
        except WebDriverException:
            key = str(id(post))
        if key in seen_keys:
            return None
        seen_keys.add(key)
        return key

    def _post_already_engaged(
        self, key: str, engage_state: Dict[str, List[str]]
    ) -> bool:
        """Report whether the saved state already holds this post key.

        WHY
          A post liked or commented in an earlier run must be skipped, so the
          run does not act on it again.

        Args
          key: str, the post dedupe key.
          engage_state: Dict[str, List[str]], the saved liked, commented and
            reposted lists.

        Returns
          bool, True when any saved list holds the key.
        """
        return (
            key in engage_state["liked"]
            or key in engage_state["commented"]
            or key in engage_state["reposted"]
        )

    def _post_is_promoted(self, post: Any) -> bool:
        """Report whether the post is promoted, treating errors as not promoted.

        WHY
          Promoted posts are skipped, but an unreadable label must not stop the
          run, so a browser error counts as an ordinary post.

        Args
          post: Any, the post element from the visible list.

        Returns
          bool, True only when the post reader says the post is promoted.
        """
        try:
            return self.engage_dom.is_promoted_post(post)
        except WebDriverException:
            return False

    def _find_post_action_bar(self, post: Any) -> Optional[Any]:
        """Return the post's action bar, or None when it cannot be found.

        WHY
          Likes and comments both start from the action bar, so a post without
          one is skipped once here instead of failing in both actions.

        Args
          post: Any, the post element from the visible list.

        Returns
          Optional[Any], the action bar element, or None when the lookup raised.
        """
        try:
            return post.find_element(By.XPATH, EngageSelectors.ACTION_BAR)
        except WebDriverException:
            return None

    def _like_profile_post(
        self,
        action_bar: Any,
        key: str,
        engage_state: Dict[str, List[str]],
        errors: List[str],
    ) -> bool:
        """Like one post and record the key on success.

        WHY
          The like is one named step, so a failure is logged and returned
          without stopping the comment step or the loop.

        Args
          action_bar: Any, the post's action bar element.
          key: str, the post dedupe key to save.
          engage_state: Dict[str, List[str]], the saved state lists to update.
          errors: List[str], the run errors list to append to.

        Returns
          bool, True when the like was made.

        MUTATIONS
          Clicks like through the post reader, adds the key to the liked list
          and waits after a successful click.
        """
        try:
            if self.engage_dom.like_from_bar(action_bar):
                engage_state["liked"].append(key)
                time.sleep(1.0)
                return True
        except WebDriverException as err:
            logger.error(f"Error liking profile post: {err.msg}")
            errors.append(f"Like failed: {err.msg}")
        return False

    def _comment_profile_post(
        self,
        post: Any,
        action_bar: Any,
        key: str,
        engage_state: Dict[str, List[str]],
        errors: List[str],
        options: PostEngageOptions,
    ) -> bool:
        """Comment on one post when the generator returns text.

        WHY
          The comment is one named step, so a missing text or a browser error
          is returned without stopping the loop.

        Args
          post: Any, the post element passed to the generator.
          action_bar: Any, the post's action bar element.
          key: str, the post dedupe key to save.
          engage_state: Dict[str, List[str]], the saved state lists to update.
          errors: List[str], the run errors list to append to.
          options: PostEngageOptions, the comment text source and the mention
            choices for this run.

        Returns
          bool, True when a comment was made.

        MUTATIONS
          Types and submits the comment through the post reader, adds the key
          to the commented list and waits after a successful comment.
        """
        comment_text = (
            options.comment_generator(post) if options.comment_generator else None
        )
        if not comment_text:
            return False
        try:
            if self.engage_dom.comment_from_bar(
                action_bar,
                comment_text,
                mention_author=options.mention_author,
                mention_position=options.mention_position,
            ):
                engage_state["commented"].append(key)
                time.sleep(2.0)
                return True
        except WebDriverException as err:
            logger.error(f"Error commenting on profile post: {err.msg}")
            errors.append(f"Comment failed: {err.msg}")
        return False

    @staticmethod
    def _profile_post_outcome(
        *,
        engaged: bool = False,
        skipped: bool = False,
        likes: int = 0,
        comments: int = 0,
        errors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Build the per-post outcome the loop applies to the run counts.

        WHY
          The handler reports what happened to one post and the parent turns
          that into counter changes, so both sides share one shape.

        Args
          engaged: bool, True when the post counted as engaged.
          skipped: bool, True when the post was passed over for a reason.
          likes: int, how many likes the post received, 0 or 1.
          comments: int, how many comments the post received, 0 or 1.
          errors: Optional[List[str]], the failure sentences for this post.

        Returns
          Dict[str, Any], the outcome with the given values and an errors list.
        """
        return {
            "engaged": engaged,
            "skipped": skipped,
            "likes": likes,
            "comments": comments,
            "errors": errors or [],
        }

    def _handle_one_profile_post(
        self,
        post: Any,
        engage_state: Dict[str, List[str]],
        seen_keys: Set[str],
        options: PostEngageOptions,
        remaining: int,
    ) -> Dict[str, Any]:
        """Like and comment on one post and report what was done.

        WHY
          One post is one unit of work, so the parent loop reads as a list of
          names and every skip or failure comes back in one outcome.

        Args
          post: Any, the post element from the visible list.
          engage_state: Dict[str, List[str]], the saved state lists to update.
          seen_keys: Set[str], the keys already handled in this run.
          options: PostEngageOptions, the like, comment and mention choices.
          remaining: int, how many posts this run may still engage.

        Returns
          Dict[str, Any], whether the post was engaged, skipped or neither,
          with the like and comment counts and any failure sentences.

        MUTATIONS
          May like or comment on the page, and adds the post key to the saved
          state lists when an action succeeds.
        """
        key = self._profile_post_key(post, seen_keys)
        if key is None:
            return self._profile_post_outcome()
        if self._post_already_engaged(key, engage_state):
            logger.info(f"Skipping post {key[:20]}... - globally engaged already.")
            return self._profile_post_outcome(skipped=True)
        if self._post_is_promoted(post):
            return self._profile_post_outcome(skipped=True)

        action_bar = self._find_post_action_bar(post)
        if action_bar is None:
            return self._profile_post_outcome(skipped=True)

        likes = 0
        comments = 0
        errors: List[str] = []
        acted = False

        if options.should_like:
            if self._like_profile_post(action_bar, key, engage_state, errors):
                likes = 1
                acted = True

        if options.should_comment and (1 if acted else 0) < remaining:
            if self._comment_profile_post(
                post,
                action_bar,
                key,
                engage_state,
                errors,
                options,
            ):
                comments = 1
                acted = True

        if not acted:
            return self._profile_post_outcome(skipped=True, errors=errors)
        return self._profile_post_outcome(
            engaged=True, likes=likes, comments=comments, errors=errors
        )
