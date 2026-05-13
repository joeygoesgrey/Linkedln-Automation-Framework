"""
Profile interaction methods for LinkedIn automation.

Why:
    Encapsulates all profile-related actions like searching, following, and
    interacting with a profile's posts in a single module.

When:
    Used when the bot needs to engage with specific profiles programmatically,
    such as in the "Operation Pursue the Investor" feature.

How:
    Provides methods to search for profiles, follow/unfollow, and interact with
    a profile's posts, using Selenium WebDriver for browser automation.
"""

import logging
import time
import urllib.parse
from typing import List, Optional, Callable, Any, Dict, Set
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from ui_selectors import ProfileSelectors, EngageSelectors

class ProfileActionsMixin:
    """Mixin class for profile-related interactions on LinkedIn."""

    def search_profile(self, name: str, bio_keywords: List[str] = None) -> Optional[str]:
        """Search for a profile and return its URL if found."""
        try:
            logging.info(f"Searching for profile: {name}")
            logging.info(f"[Stage: Pre-Search] Current browser URL: {self.driver.current_url}")

            # Use direct URL navigation to bypass brittle search UI changes
            encoded_name = urllib.parse.quote(name)
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={encoded_name}"
            self.driver.get(search_url)
            time.sleep(3)
            
            logging.info(f"[Stage: Post-Search Load] Current browser URL: {self.driver.current_url}")

            try:
                profile_elements = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, ProfileSelectors.SEARCH_RESULTS)
                    )
                )
                logging.info(f"Found {len(profile_elements)} profile elements")

                if not profile_elements:
                    logging.warning("No profile elements found")
                    return None

                if not bio_keywords:
                    for profile in profile_elements:
                        try:
                            link = profile.find_element(By.XPATH, ProfileSelectors.PROFILE_LINK)
                            href = link.get_attribute("href")
                            if href:
                                return href
                        except Exception:
                            continue
                    logging.warning("None of the profile elements contained a valid profile link.")
                    return None

                normalized_keywords = [kw.lower() for kw in bio_keywords if kw]

                for idx, profile in enumerate(profile_elements, 1):
                    try:
                        profile_text = (profile.text or "").lower()
                        logging.debug(f"Profile {idx} text sample: {profile_text[:120]}...")

                        if any(keyword in profile_text for keyword in normalized_keywords):
                            logging.info(
                                "Match found in profile %d based on bio keywords.",
                                idx,
                            )
                            link = profile.find_element(By.XPATH, ProfileSelectors.PROFILE_LINK)
                            return link.get_attribute("href")
                    except Exception as err:
                        logging.debug(f"Error processing profile {idx}: {err}")
                        continue

                logging.info("No matching bio found, returning first valid result")
                for profile in profile_elements:
                    try:
                        link = profile.find_element(By.XPATH, ProfileSelectors.PROFILE_LINK)
                        href = link.get_attribute("href")
                        if href:
                            return href
                    except Exception:
                        continue
                return None

            except Exception as find_err:
                logging.error(f"Error finding profile elements: {find_err}")
                self.driver.save_screenshot("search_error.png")
                logging.info("Screenshot saved as search_error.png")
                return None

        except Exception as e:
            logging.error(f"Error in search_profile: {str(e)}", exc_info=True)
            return None


    def follow_profile(self) -> bool:
        """Follow the current profile if not already following.
        
        Returns:
            bool: True if followed, False if already following or error
        """
        try:
            follow_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, ProfileSelectors.FOLLOW_BUTTON))
            )
            if "Following" not in follow_button.text:
                follow_button.click()
                return True
            return False
        except Exception as e:
            logging.error(f"Error following profile: {str(e)}")
            return False

    def open_profile_posts_view(self) -> bool:
        """Ensure the profile's "Show all posts" view is open."""
        try:
            current_url = self.driver.current_url or ""
            if "recent-activity" not in current_url:
                import urllib.parse
                parsed = urllib.parse.urlparse(current_url)
                base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if not base_url.endswith('/'):
                    base_url += '/'
                
                recent_activity_url = f"{base_url}recent-activity/all/"
                logging.info(f"Navigating directly to recent activity: {recent_activity_url}")
                self.driver.get(recent_activity_url)
                time.sleep(3)
                
            # Click the "Posts" tab to filter out comments/reactions
            try:
                posts_tab = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, ProfileSelectors.POSTS_TAB_BUTTON))
                )
                posts_tab.click()
                time.sleep(2)
                logging.info("Clicked 'Posts' tab in recent activity.")
            except Exception as e:
                logging.warning(f"Could not click 'Posts' tab, continuing with current activity view: {e}")

            return True
        except Exception as e:
            logging.error(f"Error opening profile posts view: {str(e)}")
            return False

    def get_profile_post_urls(self, max_posts: int = 5) -> List[str]:
        """Get URLs of the most recent posts from the current profile.
        
        Args:
            max_posts: Maximum number of post URLs to return
            
        Returns:
            List of post URLs (up to max_posts)
        """
        try:
            self.open_profile_posts_view()

            last_height = self.driver.execute_script("return document.body.scrollHeight")
            post_urls: set[str] = set()

            while len(post_urls) < max_posts:
                posts = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    ProfileSelectors.POST_LINKS
                )

                for post in posts:
                    href = post.get_attribute("href")
                    if href and "/posts/" in href and href not in post_urls:
                        post_urls.add(href)
                        if len(post_urls) >= max_posts:
                            break

                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    try:
                        self.driver.execute_script("window.scrollTo(0, Math.max(document.body.scrollHeight - window.innerHeight, 0));")
                    except Exception:
                        pass
                    time.sleep(1.5)
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        break
                last_height = new_height

            return list(post_urls)[:max_posts]

        except Exception as e:
            logging.error(f"Error getting profile posts: {str(e)}")
            return []

    def engage_profile_posts(
        self,
        max_posts: int,
        should_like: bool = True,
        should_comment: bool = True,
        comment_generator: Optional[Callable[[Any], Optional[str]]] = None,
        mention_author: bool = True,
        mention_position: str = 'prepend',
    ) -> Dict[str, Any]:
        """Interact with visible posts on the current profile page."""
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

        # Load global engage state to prevent double-engaging across runs
        engage_state = {}
        try:
            engage_state = self._load_engage_state()
            if not isinstance(engage_state.get('liked'), list): engage_state['liked'] = []
            if not isinstance(engage_state.get('commented'), list): engage_state['commented'] = []
            if not isinstance(engage_state.get('reposted'), list): engage_state['reposted'] = []
        except Exception:
            engage_state = {'liked': [], 'commented': [], 'reposted': []}

        seen_keys: Set[str] = set()
        stalled = 0

        while results["posts_engaged"] < max_posts and stalled < 8:
            try:
                posts = self._find_visible_posts(limit=12)
            except Exception as err:
                logging.error(f"Error locating profile posts: {err}")
                results["errors"].append(f"Locate posts failed: {err}")
                posts = []

            if not posts:
                stalled += 1
                try:
                    self._scroll_feed(0.8, 1.6)
                except Exception:
                    self.driver.execute_script("window.scrollBy(0, window.innerHeight * 0.9);")
                time.sleep(1.2)
                continue

            progress = False

            for post in posts:
                if results["posts_engaged"] >= max_posts:
                    break

                try:
                    urn = self._extract_post_urn(post)
                    key = self._post_dedupe_key(post, urn)
                except Exception:
                    key = str(id(post))

                if key in seen_keys:
                    continue
                seen_keys.add(key)

                # Skip if we've globally engaged with this specific text/URN before
                if key in engage_state['liked'] or key in engage_state['commented'] or key in engage_state['reposted']:
                    logging.info(f"Skipping post {key[:20]}... - globally engaged already.")
                    results["skipped"] += 1
                    continue

                try:
                    if self._is_promoted_post(post):
                        results["skipped"] += 1
                        continue
                except Exception:
                    pass

                try:
                    action_bar = post.find_element(By.XPATH, EngageSelectors.ACTION_BAR)
                except Exception:
                    results["skipped"] += 1
                    continue

                acted = False

                if should_like:
                    try:
                        if self._like_from_bar(action_bar):
                            results["likes"] += 1
                            engage_state['liked'].append(key)
                            acted = True
                            time.sleep(1.0)
                    except Exception as err:
                        logging.error(f"Error liking profile post: {err}")
                        results["errors"].append(f"Like failed: {err}")

                if should_comment and results["posts_engaged"] + (1 if acted else 0) < max_posts:
                    comment_text = comment_generator(post) if comment_generator else None
                    if comment_text:
                        try:
                            if self._comment_from_bar(
                                action_bar,
                                comment_text,
                                mention_author=mention_author,
                                mention_position=mention_position,
                            ):
                                results["comments"] += 1
                                engage_state['commented'].append(key)
                                acted = True
                                time.sleep(2.0)
                        except Exception as err:
                            logging.error(f"Error commenting on profile post: {err}")
                            results["errors"].append(f"Comment failed: {err}")

                if acted:
                    progress = True
                    results["posts_engaged"] += 1
                    try:
                        self._save_engage_state(engage_state)
                    except Exception:
                        pass
                    time.sleep(1.0)
                else:
                    results["skipped"] += 1

            if progress:
                stalled = 0
            else:
                stalled += 1
                try:
                    self._scroll_feed(0.8, 1.6)
                except Exception:
                    self.driver.execute_script("window.scrollBy(0, window.innerHeight * 0.9);")
                time.sleep(1.2)

        return results

    def like_post(self) -> bool:
        """Like the current post if not already liked.
        
        Returns:
            bool: True if liked, False if already liked or error
        """
        try:
            # Find the main post container
            post_container = self.driver.find_element(
                By.CSS_SELECTOR, 
                ProfileSelectors.POST_CONTAINER
            )
            
            # Find the action bar
            action_bar = post_container.find_element(
                By.CSS_SELECTOR,
                ProfileSelectors.ACTION_BAR_CSS
            )
            
            # Use the _like_from_bar method from EngageDomMixin
            return self._like_from_bar(action_bar)
            
        except Exception as e:
            logging.error(f"Error in like_post: {str(e)}")
            return False

    def comment_on_post(self, comment_text: str, mention_author: bool = False, 
                       mention_position: str = 'append') -> bool:
        """Add a comment to the current post.
        
        Args:
            comment_text: Text of the comment to post
            mention_author: Whether to mention the post author in the comment
            mention_position: Where to place the mention ('prepend' or 'append')
            
        Returns:
            bool: True if comment was posted, False otherwise
        """
        try:
            # Find the main post container
            post_container = self.driver.find_element(
                By.CSS_SELECTOR, 
                ProfileSelectors.POST_CONTAINER
            )
            
            # Find the action bar
            action_bar = post_container.find_element(
                By.CSS_SELECTOR,
                ProfileSelectors.ACTION_BAR_CSS
            )
            
            # Use the _comment_from_bar method from EngageDomMixin
            return self._comment_from_bar(
                action_bar,
                comment_text,
                mention_author=mention_author,
                mention_position=mention_position
            )
            
        except Exception as e:
            logging.error(f"Error in comment_on_post: {str(e)}")
            return False