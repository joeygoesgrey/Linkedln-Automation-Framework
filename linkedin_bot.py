"""High-level controller for orchestrating LinkedIn automation workflows.

Why:
    Provide a cohesive object that wires the browser driver, content
    generation, AI helpers, and UI interaction mixins so callers interact with
    a single abstraction.

When:
    Instantiated by CLI scripts or tests whenever posting content, scheduling,
    or engaging with the feed is required.

How:
    Sets up Selenium via :class:`DriverFactory`, configures AI clients,
    delegates UI operations to :class:`linkedin_ui.LinkedInInteraction`, and
    exposes convenience methods for posting custom text, processing topic files,
    and engaging with feed items.
"""

import os
import re
import json
import time
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from openai_client import ContentCalendarRequest
from selenium.webdriver.common.by import By   
import config
from driver import DriverFactory
from content_generator import ContentGenerator
from openai_client import OpenAIClient
from linkedin_interaction import LinkedInInteraction
from linkedin_ui.post_extractor import PostExtractor


class LinkedInBot:
    """Composite orchestrator that drives LinkedIn automation flows.

    Why:
        Aggregate driver management, content generation, and UI interactions so
        upstream callers focus on workflow intent rather than wiring.

    When:
        Create once per CLI invocation or integration test to handle posting or
        engagement tasks; the instance remains valid until :meth:`close` runs.

    How:
        Initialises Selenium via :class:`DriverFactory`, loads AI helpers, wraps
        the UI mixins through :class:`LinkedInInteraction`, and exposes helper
        methods that chain these subsystems together.
    """

    def __init__(self, use_openai: bool = True) -> None:
        """Instantiate the bot and log into LinkedIn immediately.

        Why:
            Many workflows assume an authenticated session; logging in upfront
            reduces surprise and simplifies later method implementations.

        When:
            Called whenever a new automation run is needed. A fresh instance is
            recommended per run to avoid stale browser state.

        How:
            Spins up a Selenium driver via :class:`DriverFactory`, prepares
            :class:`ContentGenerator` and optionally :class:`OpenAIClient`, then
            constructs :class:`LinkedInInteraction` and :class:`PostExtractor`
            before invoking :meth:`LinkedInInteraction.login`.

        Args:
            use_openai (bool): Toggle for initialising the OpenAI client; useful
                for offline or no-AI scenarios.
        """
        self.driver = DriverFactory.setup_driver()
        self.openai_client = OpenAIClient() if (use_openai and config.OPENAI_API_KEY) else None
        self.content_generator = ContentGenerator(ai_client=self.openai_client)
        self.linkedin = LinkedInInteraction(self.driver)
        self.post_extractor = PostExtractor(self.driver)
        
        # Login to LinkedIn
        self.linkedin.login()

    def _get_random_perspective(self, perspectives: List[str]) -> str:
        """Select a perspective token for AI comment generation.

        Why:
            Ensures the engage stream rotates through varied tones (funny,
            motivational, insightful) without duplicating logic across call
            sites.

        When:
            Used internally when constructing AI prompts for engagement flows.

        How:
            Normalises the input list, replaces ``"random"`` with the default
            pool, and returns a random choice.

        Args:
            perspectives (list[str]): Candidate perspective labels, possibly
                including ``"random"``.

        Returns:
            str: A concrete perspective ready for prompt building.
        """
        standard_perspectives = ["funny", "motivational", "insightful"]

        if not perspectives or "random" in perspectives:
            if perspectives == ["random"]:
                return random.choice(standard_perspectives)

            valid_perspectives = [p for p in perspectives if p != "random"]
            return random.choice(valid_perspectives or standard_perspectives)

        return random.choice(perspectives)

    def process_topics(
        self, 
        topic_file_path: Optional[str] = None, 
        image_directory: Optional[str] = None, 
        schedule_date: Optional[str] = None, 
        schedule_time: Optional[str] = None,
        engage_with_feed: bool = False,
        max_posts_to_engage: int = 3,
        perspectives: Optional[List[str]] = None,
        no_images: bool = False
    ) -> Dict[str, Any]:
        """Publish a post sourced from a topics file and optionally engage feed posts.

        Why:
            Automates daily posting by drawing from a backlog of ideas while also
            kicking off lightweight engagement to boost reach.

        When:
            Triggered by the default CLI flow or schedulers that process topic
            queues at regular intervals.

        How:
            Loads topics (falling back to defaults), generates content via
            :class:`ContentGenerator`, selects media, posts via
            :class:`LinkedInInteraction`, optionally runs the engage stream, and
            trims the processed topic from the source file.

        Args:
            topic_file_path (str | None): Path to a newline-delimited topic file
                or ``None`` to use built-in templates.
            image_directory (str | None): Folder containing candidate images.
            schedule_date (str | None): Optional date string for scheduled posts.
            schedule_time (str | None): Optional time string for scheduled posts.
            engage_with_feed (bool): Whether to follow up with feed engagement.
            max_posts_to_engage (int): Maximum feed items to touch during
                engagement.
            perspectives (list[str] | None): Preferred AI perspectives for
                comments if engagement is enabled.
            no_images (bool): Whether to skip image uploads.

        Returns:
            dict: Outcome metadata including posting success and engagement
            stats.
        """
        # Pydantic validation (Standard 3)
        from models import TopicsModel
        try:
            validated = TopicsModel(
                topic_file_path=topic_file_path or config.DEFAULT_TOPIC_FILE,
                image_directory=image_directory,
                schedule_date=schedule_date,
                schedule_time=schedule_time,
                engage_with_feed=engage_with_feed,
                max_posts_to_engage=max_posts_to_engage,
                perspectives=perspectives,
                no_images=no_images
            )
        except Exception as e:
            logging.error(f"Validation failed for process_topics: {e}")
            raise

        topic_file_path = validated.topic_file_path
        perspectives = validated.perspectives or ["funny", "motivational", "insightful"]
        
        results: Dict[str, Any] = {
            "post_created": False,
            "post_url": None,
            "engagement": None,
            "perspectives_used": []
        }

        logging.info(f"Processing topics from {topic_file_path}")

        try:
            topics: List[str] = []
            topics_file_exists = False

            if topic_file_path and Path(topic_file_path).exists():
                topics_file_exists = True
                with open(topic_file_path, "r") as f:
                    topics = [t.strip() for t in f.readlines() if t.strip()]

            if topics:
                chosen_topic = random.choice(topics)
                logging.info(f"Found {len(topics)} topics. Selected: {chosen_topic}")
            else:
                default_topics = getattr(self.content_generator, "_default_posts", {
                    "leadership", "productivity", "technology",
                    "networking", "remote work", "iot", "ai", "blockchain"
                })
                chosen_topic = random.choice(list(default_topics))
                logging.info(f"No topics file found. Using built-in topic: {chosen_topic}")
            
            # Generate content
            post_content = self.content_generator.generate_post_content(chosen_topic)

            if config.ENABLE_TEXT_PREPROCESSING:
                from text_utils import preprocess_for_ai
                post_content = preprocess_for_ai(
                    post_content,
                    summarize_ratio=config.SUMMARIZE_RATIO if config.SUMMARIZE_INPUT else None,
                    max_chars=config.MAX_INPUT_CHARS
                )
            
            images_to_post = []
            if not no_images:
                images_to_post = self._select_images(image_directory)
            
            if self.linkedin.login():
                post_success = self.linkedin.post_to_linkedin(
                    post_content,
                    image_paths=images_to_post,
                    schedule_date=schedule_date,
                    schedule_time=schedule_time,
                )
                results["post_created"] = post_success
                
                if post_success and engage_with_feed:
                    logging.info("Post successful. Engaging with feed...")
                    try:
                        engagement_results = self.linkedin.engage_stream(
                            mode="comment",
                            comment_text=json.dumps({
                                "perspectives": perspectives,
                                "max_tokens": 150,
                                "temperature": 0.7
                            }),
                            max_actions=max_posts_to_engage,
                            include_promoted=False
                        )
                        results["engagement"] = {
                            "success": True,
                            "count": engagement_results.get("count", 0),
                            "errors": engagement_results.get("errors", []),
                            "perspectives_used": perspectives[:engagement_results.get("count", 0)]
                        }
                    except Exception as e:
                        logging.error(f"Error engaging with feed: {e}")
                        results["engagement"] = {"success": False, "error": str(e)}

                if post_success and topics_file_exists and chosen_topic in topics:
                    self._update_topics_file(topic_file_path, topics, chosen_topic)
                    
            time.sleep(random.uniform(5, 10))

        except Exception:
            logging.error("An error occurred while processing topics.", exc_info=True)

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
        no_images: bool = False
    ) -> bool:
        """Publish a caller-supplied post with optional media and mentions.

        Why:
            Supports ad-hoc messaging outside the topic workflow while reusing
            the same resilient Selenium interactions.

        When:
            Used by CLI `--post-text` runs or tests wanting deterministic
            content.

        How:
            Validates input, injects inline mention placeholders, gathers media
            (explicit paths first, then directory sampling), ensures login, and
            delegates posting to :meth:`LinkedInInteraction.post_to_linkedin`.

        Args:
            post_text (str): Content to publish.
            image_directory (str | None): Folder to sample images from when
                ``image_paths`` is empty.
            mention_anchors (list[str] | None): Text anchors preceding mentions.
            mention_names (list[str] | None): Display names matching anchors.
            image_paths (list[str] | None): Explicit file paths to attach.
            schedule_date (str | None): Optional scheduling date.
            schedule_time (str | None): Optional scheduling time.
            no_images (bool): Whether to skip image uploads.

        Returns:
            bool: ``True`` on apparent success, ``False`` otherwise.
        """
        # Standard 3: Validation logic at start
        if not isinstance(post_text, str) or not post_text.strip():
            logging.error("post_custom_text requires a non-empty post_text string")
            return False
        if not isinstance(no_images, bool):
            raise TypeError(f"no_images must be a bool, got {type(no_images)}")

        try:
            processed_text = self._apply_anchor_mentions(post_text, mention_anchors, mention_names)
            
            images_to_post = []
            if not no_images:
                images_to_post = [str(Path(p).absolute()) for p in (image_paths or []) if Path(p).exists()]
                if not images_to_post:
                    images_to_post = self._select_images(image_directory)

            if not self.linkedin.login():
                logging.error("Login failed before custom post")
                return False

            ok = self.linkedin.post_to_linkedin(
                processed_text,
                image_paths=images_to_post,
                schedule_date=schedule_date,
                schedule_time=schedule_time,
            )
            logging.info("Successfully posted custom text" if ok else "Failed to post custom text")
            return ok

        except Exception:
            logging.error("An error occurred in post_custom_text.", exc_info=True)
            return False

    def _apply_anchor_mentions(self, post_text: str, anchors: Optional[List[str]], names: Optional[List[str]]) -> str:
        """Inject ``@{Name}`` tokens after configured anchor phrases.

        Why:
            Allow users to specify where mentions belong without manually
            crafting placeholders.

        When:
            Called before composing text if `mention_anchors` and
            `mention_names` are provided.

        How:
            Iterates through provided anchor/name pairs, constructs regex
            patterns that respect word boundaries, and substitutes the first
            occurrence with an embedded ``@{name}`` token.

        Args:
            post_text (str): Original content.
            anchors (list[str] | None): Anchor phrases preceding a mention.
            names (list[str] | None): Corresponding display names.

        Returns:
            str: Post text with inline mention placeholders applied.
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
                        logging.info(f"Anchor not found: '{anchor}'")
                except Exception as re_err:
                    logging.info(f"Anchor substitution failed for '{anchor}': {re_err}")
            return result
        except Exception as e:
            logging.info(f"_apply_anchor_mentions failed; returning original text: {e}")
            return post_text

    def _select_images(self, image_directory: Optional[str]) -> List[str]:
        """Pick up to three random images from a directory.

        Why:
            Avoid repetitive manual selection while still adding media variety to
            posts sourced from topic files.

        When:
            Used when the caller supplies an image directory but no explicit
            paths.

        How:
            Validates the directory, filters supported extensions, and samples
            up to three unique files.

        Args:
            image_directory (str | None): Directory path to scan for images.

        Returns:
            list[str]: Absolute file paths suitable for Selenium uploads.
        """
        if not image_directory:
            return []

        try:
            image_dir = Path(image_directory)
            if not image_dir.exists() or not image_dir.is_dir():
                logging.warning(f"Image directory does not exist: {image_directory}")
                return []

            image_files = [
                str(f) for f in image_dir.glob("*")
                if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif")
            ]

            if image_files:
                return random.sample(image_files, min(3, len(image_files)))

            logging.info("No images found in directory")
            return []
        except Exception as e:
            logging.error(f"Error selecting images: {e}")
            return []

    def _update_topics_file(self, file_path: str, topics: List[str], posted_topic: str) -> None:
        """Persist topic progress by removing the used idea and logging history.

        Why:
            Prevents reposting the same topic and keeps an audit trail of what
            went live and when.

        When:
            Invoked after a successful post originating from a topics file.

        How:
            Removes the chosen topic from the in-memory list, rewrites the file
            with remaining entries, and appends a timestamped record to a
            `<topics>_posted` companion file.

        Args:
            file_path (str): Original topics file path.
            topics (list[str]): Remaining topics.
            posted_topic (str): Topic that was just published.

        Returns:
            None
        """
        try:
            topics.remove(posted_topic)
            path = Path(file_path)
            path.write_text("\n".join(topics) + ("\n" if topics else ""), encoding="utf-8")
            logging.info(f"Updated topics file. {len(topics)} topics remaining.")

            stem = path.stem or "topics"
            suffix = path.suffix or ".txt"
            history_path = path.with_name(f"{stem}_posted{suffix}")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with history_path.open("a", encoding="utf-8") as history_file:
                history_file.write(f"{timestamp} | {posted_topic}\n")
            logging.info("Recorded posted topic in %s", history_path)
        except ValueError:
            logging.warning("Posted topic '%s' not found in %s", posted_topic, file_path)
        except Exception as e:
            logging.error(f"Error updating topics file: {e}")

    def generate_content_calendar(
        self, 
        niche: str, 
        output_file: str = "calendar.txt", 
        total_posts: int = 30
    ) -> bool:
        """Produce a multi-day content plan using OpenAI and save to disk.

        Args:
            niche: The industry or topic niche.
            output_file: Path to save the generated calendar.
            total_posts: Number of post ideas to generate.
            
        Returns:
            bool: True if generation and saving succeeded.
        """
        # Pydantic validation (Standard 3)
        from models import CalendarModel
        try:
            validated = CalendarModel(
                niche=niche,
                output_file=output_file,
                total_posts=total_posts
            )
        except Exception as e:
            logging.error(f"Validation failed for generate_content_calendar: {e}")
            raise

        if not self.openai_client:
            logging.error("OpenAI client not initialized. Cannot generate calendar.")
            return False
            
        
        logging.info(f"Generating {validated.total_posts}-day content calendar for niche: {validated.niche}")
        
        request = ContentCalendarRequest(
            niche=validated.niche,
            goal="Establish thought leadership and build community",
            audience="Professionals, enthusiasts, and potential collaborators",
            tone="Informative, engaging, and authentic",
            content_types=["text", "images", "personal stories", "industry news"],
            frequency="Daily",
            total_posts=validated.total_posts,
            hashtags=[validated.niche.replace(" ", ""), "Growth", "Networking", "Tech"]
        )
        
        try:
            calendar_text = self.openai_client.generate_content_calendar(request)
            
            with open(validated.output_file, "w", encoding="utf-8") as f:
                f.write(calendar_text)
                
            logging.info(f"Successfully generated calendar and saved to {validated.output_file}")
            return True
        except Exception as e:
            logging.error(f"Failed to generate or save content calendar: {e}")
            return False

    def close(self) -> None:
        """Terminate the Selenium session and release resources.
        
        Why:
            Avoid lingering browser processes and free OS resources once work is
            complete.
        
        When:
            Call after finishing posting or engagement workflows.
        
        How:
            Invokes :meth:`webdriver.Chrome.quit` and logs the outcome.
            
        Returns:
            None
        """
        try:
            self.driver.quit()
            logging.info("Driver session ended cleanly.")
        except Exception as e:
            logging.error(f"Error closing driver: {e}")


    def pursue_investor(
        self,
        profile_name: str,
        max_posts: int = 5,
        should_follow: bool = True,
        should_like: bool = True,
        should_comment: bool = True,
        comment_perspectives: Optional[List[str]] = None,
        bio_keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Pursue and engage with a specific person's profile.
        
        Args:
            profile_name: Name of the person to engage with
            max_posts: Maximum number of posts to engage with
            should_follow: Whether to follow the profile
            should_like: Whether to like posts
            should_comment: Whether to comment on posts
            comment_perspectives: List of perspectives for AI comments
                
        Returns:
            Dict containing results and any errors
        """
        # Pydantic validation (Standard 3)
        from models import PursueModel
        try:
            validated = PursueModel(
                profile_name=profile_name,
                max_posts=max_posts,
                should_follow=should_follow,
                should_like=should_like,
                should_comment=should_comment,
                comment_perspectives=comment_perspectives,
                bio_keywords=bio_keywords
            )
        except Exception as e:
            logging.error(f"Validation failed for pursue_investor: {e}")
            raise

        results = {
            'profile': validated.profile_name,
            'followed': False,
            'posts_engaged': 0,
            'likes_given': 0,
            'comments_made': 0,
            'errors': []
        }
        
        try:
            # Ensure we are logged in before pursuing
            if not self.linkedin.login():
                error_msg = "Aborting pursue_investor: Failed to login to LinkedIn."
                logging.error(error_msg)
                results['errors'].append(error_msg)
                return results

            # Search for the profile with bio keywords
            logging.info(f"Searching for profile: {validated.profile_name}")
            if validated.bio_keywords:
                logging.info(f"Looking for bio containing: {', '.join(validated.bio_keywords)}")
                
            profile_url = self.linkedin.search_profile(
                validated.profile_name,
                bio_keywords=validated.bio_keywords
            )
            
            if not profile_url:
                raise ValueError(f"Could not find matching profile for {validated.profile_name}")
                
            # Navigate to profile
            logging.info(f"Navigating to profile: {profile_url}")
            self.linkedin.driver.get(profile_url)
            time.sleep(3)  # Wait for profile to load

            # Follow the profile if requested
            if validated.should_follow:
                try:
                    if self.linkedin.follow_profile():
                        results['followed'] = True
                        logging.info(f"Successfully followed {validated.profile_name}")
                except Exception as e:
                    error_msg = f"Failed to follow profile: {str(e)}"
                    results['errors'].append(error_msg)
                    logging.error(error_msg)
            
            # Engage directly on the profile's posts page
            logging.info(f"Opening profile posts view and engaging up to {validated.max_posts} posts")
            if not self.linkedin.open_profile_posts_view():
                logging.warning("Could not confirm profile posts view; continuing with current page")

            comment_generator = None
            if validated.should_comment:
                def build_comment(post_root):  # type: ignore[return-type]
                    base_text = "Great post! Thanks for sharing."
                    if self.openai_client:
                        try:
                            post_text = self.post_extractor.extract_text(post_root)
                        except Exception:
                            post_text = ""
                        if post_text:
                            try:
                                perspective = self._get_random_perspective(
                                    validated.comment_perspectives or ["insightful", "motivational", "funny"]
                                )
                                return self.openai_client.generate_comment(
                                    post_text=post_text,
                                    perspective=perspective,
                                    max_tokens=180,
                                    temperature=0.7,
                                )
                            except Exception as err:
                                logging.error(f"AI comment generation failed: {err}")
                    return base_text
                comment_generator = build_comment

            engagement = self.linkedin.engage_profile_posts(
                max_posts=validated.max_posts,
                should_like=validated.should_like,
                should_comment=validated.should_comment,
                comment_generator=comment_generator,
                mention_author=True,
                mention_position='prepend',
            )

            results['posts_engaged'] = engagement.get('posts_engaged', 0)
            results['likes_given'] = engagement.get('likes', 0)
            results['comments_made'] = engagement.get('comments', 0)
            
            logging.info(
                f"Engagement summary for {validated.profile_name}: "
                f"actions={results['posts_engaged']}, skipped={engagement.get('skipped', 0)}"
            )

            return results

        except Exception as e:
            error_msg = f"Error pursuing investor {profile_name}: {str(e)}"
            results['errors'].append(error_msg)
            logging.error(error_msg, exc_info=True)
            return results
