"""Content generation helpers that use OpenAI with local fallbacks.

WHY
  Keep prompts, local templates and fallbacks in one place, so posting flows only
  ask for post text and never branch on AI availability themselves.
"""

import logging
import random
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from laf.ai.client import OpenAIClient
from laf.config import CONFIG, Config
from laf.errors import AiError
from laf.models import NicheModel

logger = logging.getLogger(__name__)


class ContentGenerator:
    """Write LinkedIn copy with OpenAI or local fallbacks.

    WHY
      Keep one tone and structure across every call, so the bot can keep posting
      when OpenAI is off or fails.
    """

    def __init__(
        self, ai_client: Optional[OpenAIClient] = None, config: Config = CONFIG
    ):
        """Prepare the config and the cached templates for this session.

        WHY
          Read config and template files once at build time, so each post does
          not repeat file reads or client setup.

        Args
          ai_client: Optional[OpenAIClient], a client from the caller, or None.
          config: Config, the settings passed by the caller or the CONFIG default.

        MUTATIONS
          Stores config, the OpenAI client, and the default and custom templates
          on the instance.
        """
        self.config = config
        self.openai_client = ai_client
        if not self.openai_client and self.config.openai_api_key:
            self.openai_client = OpenAIClient()

        self._default_posts = self._get_default_templates()
        self._custom_posts = self._load_custom_posts(self.config.custom_posts_file)

    def _get_default_templates(self):
        """Return the built-in post templates.

        WHY
          Keep a known set of ready posts, so the bot can still write something
          when AI is off or fails.

        Returns
          dict[str, str], template text keyed by topic keyword.
        """
        return {
            "leadership": (
                "True leadership isn't about being in charge. It's about taking care of "
                "those in your charge. Focus on empathy and clear communication today. "
                "#Leadership #Management #Growth"
            ),
            "productivity": (
                "Efficiency is doing things right; effectiveness is doing the right "
                "things. What's one task you can simplify or delegate today? "
                "#Productivity #Efficiency #Success"
            ),
            "technology": (
                "The best way to predict the future is to create it. How are you "
                "leveraging new tech to stay ahead of the curve? "
                "#Technology #Innovation #Future"
            ),
            "networking": (
                "Your network is your net worth. Take 5 minutes today to reach out to "
                "someone you haven't spoken to in a while. "
                "#Networking #Community #Career"
            ),
            "remote work": (
                "Remote work is not just a trend, it is a fundamental shift in how we "
                "think about work and life. Balance is key. "
                "#RemoteWork #WorkLifeBalance #FutureOfWork"
            ),
            "iot": (
                "Internet of Things (IoT) is connecting the physical and digital worlds "
                "in ways we never imagined. Seamless integration is the goal. "
                "#IoT #TechTrends #SmartSystems"
            ),
            "ai": (
                "Artificial Intelligence is no longer science fiction. It's a tool that "
                "can augment human potential when used ethically and thoughtfully. "
                "#AI #MachineLearning #Ethics"
            ),
            "blockchain": (
                "Trust is at the heart of blockchain technology. Beyond crypto, it's "
                "about decentralised verification and security. "
                "#Blockchain #Security #Trust"
            ),
        }

    def _load_custom_posts(self, path):
        """Read the user's own post templates from a file.

        WHY
          Let a user keep their own voice when AI is off, so local posts still
          sound right.

        Args
          path: str, the custom template file path from config.custom_posts_file.

        Returns
          list[str], the non-empty lines of the file, or an empty list when the
          file is missing or unreadable.
        """
        if not path or not Path(path).exists():
            return []

        try:
            with open(path, "r") as f:
                lines = [ln.strip() for ln in f.readlines()]
            posts = [ln for ln in lines if ln]
            logger.info("Loaded %d custom post templates from %s", len(posts), path)
            return posts
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Failed to load custom posts from %s: %s", path, e)
            return []

    def _generate_local_post(self, topic, default_post=None):
        """Build a post from templates or random phrase parts.

        WHY
          Keep posting possible when AI is off or fails, so a run does not stop
          for want of a post.

        Args
          topic: str, the subject to work into the text, from the caller.
          default_post: Optional[str], the fallback text from the caller.

        Returns
          str, the post text with the marketing blurb.
        """
        # 1) Use a custom template if available
        if getattr(self, "_custom_posts", None):
            try:
                tpl = random.choice(self._custom_posts)
                text = tpl.format(topic=topic)
                if len(text) > self.config.max_post_length:
                    text = text[: self.config.max_post_length - 3].rstrip() + "..."
                return self._append_marketing_blurb(text)
            except (KeyError, IndexError, ValueError) as e:
                logger.debug("Custom template render failed, using randomized text: %s", e)

        # 2) Build a randomized post from phrase sets
        intros = [
            "Quick thought on",
            "A practical take on",
            "Some reflections about",
            "What I’m learning from",
            "Here’s a perspective on",
        ]
        values = [
            "focus on clear outcomes over busywork",
            "ship small, iterate fast, and listen to feedback",
            "keep systems simple and resilient",
            "optimize for long‑term maintainability",
            "blend data with intuition when deciding",
        ]
        actions = [
            "what’s one tip that helped you most?",
            "how are you approaching this right now?",
            "what trade‑offs do you consider first?",
            "what’s a pattern you’d repeat?",
            "what did you try that didn’t work?",
        ]
        hashtags_pool = [
            "#LeadershipInsights",
            "#Productivity",
            "#Tech",
            "#AI",
            "#IoT",
            "#DigitalTransformation",
            "#CareerGrowth",
            "#Engineering",
            "#SaaS",
        ]
        intro = random.choice(intros)
        value = random.choice(values)
        action = random.choice(actions)
        hashtags = " ".join(random.sample(hashtags_pool, k=min(3, len(hashtags_pool))))
        post = (
            f"{intro} {topic}.\n\n"
            f"Key principle: {value}.\n\n"
            f"Curious to hear from this community. {action}\n\n"
            f"{hashtags}"
        )
        if len(post) > self.config.max_post_length:
            post = post[: self.config.max_post_length - 3].rstrip() + "..."
        final_post = post or (default_post or f"Sharing a few thoughts on {topic} today.")
        return self._append_marketing_blurb(final_post)

    def _append_marketing_blurb(self, text: str) -> str:
        """Add a marketing call to action to post text.

        WHY
          Keep the project link in local posts, so every post points readers to
          the project when marketing is on.

        Args
          text: str, the post text to extend.

        Returns
          str, the text with the call to action when marketing is on and the
          project URL is missing.
        """
        if not text or not self.config.marketing_mode:
            return text
        if self.config.project_url in text:
            return text.strip()
        tagline = f"🔗 Explore {self.config.project_name}: {self.config.project_tagline}"
        return f"{text.strip()}\n\n{tagline}"

    def generate_post_content(self, topic: str) -> str:
        """Write post text for a topic, using AI or a local fallback.

        WHY
          Give a topic run usable copy even when OpenAI is off or fails, so the
          run still produces a post.

        Args
          topic: str, the subject to write about, from the caller.

        Returns
          str, the post text with any marketing blurb.

        Raises
          ValidationError: when the topic fails the NicheModel check.
        """
        # Pydantic validation (Standard 3)
        try:
            validated = NicheModel(niche=topic or "")
            topic = validated.niche
        except ValidationError as e:
            logger.error("Topic validation failed for generation: %s", e)
            raise

        logger.info("Generating post content for topic: %s", topic)

        # Try to match the topic to a key in our default posts dictionary
        matched_post = None
        matched_key = None
        topic_lower = topic.lower()
        for key in self._default_posts:
            if key in topic_lower:
                matched_post = self._default_posts[key]
                matched_key = key
                break

        # If no match found, use a generic professional post
        default_post = (
            matched_post
            or (
                f"Exploring the fascinating world of {topic} today. Innovation and "
                f"adaptation are key in this rapidly evolving landscape. I'd love to "
                f"hear your insights on this topic! #ProfessionalDevelopment "
                f"#IndustryTrends #LinkedIn"
            )
        )

        if matched_post:
            logger.info(
                "Using matched template for '%s' keyword in topic: '%s'", matched_key, topic
            )
        else:
            logger.info("Using generic template for topic: '%s'", topic)

        try:
            if not self.openai_client:
                logger.info("OpenAI client not initialized. Using local fallback content.")
                return self._generate_local_post(topic, default_post)

            logger.info("Generating content with OpenAI API...")
            post_text = self.openai_client.generate_post(topic)

            logger.info("Successfully generated post content with OpenAI")
            # OpenAI post generation already includes marketing tail if configured
            return post_text

        except AiError as e:
            logger.error("Failed to generate post content with OpenAI: %s", e)
            return self._generate_local_post(topic, default_post)
