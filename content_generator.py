"""Content generation helpers leveraging OpenAI with graceful fallbacks.

Why:
    Centralise AI prompts, local templates, and fallback logic so posting flows
    can focus on composing LinkedIn UI interactions.

When:
    Instantiated during bot setup whenever auto-generated content is required.

How:
    Utilises OpenAIClient for content generation, loads local templates, 
    and exposes methods to generate posts and request content calendars.
"""

import logging
import random
from pathlib import Path
from typing import List, Dict, Any, Optional
from models import NicheModel
import config
from openai_client import OpenAIClient


class ContentGenerator:
    """Generate LinkedIn-ready copy using OpenAI or local fallbacks.

    Why:
        Maintain a consistent tone and structure without duplicating prompt
        logic across call sites.

    When:
        Created alongside :class:`LinkedInBot` and reused for each post.

    How:
        Uses OpenAIClient, caches default and custom templates, and exposes
        helpers for producing AI or locally generated post text.
    """
    
    def __init__(self, ai_client: Optional[OpenAIClient] = None):
        """Prepare configuration and cached templates.

        Why:
            Avoid repeating configuration steps and file reads for every
            generated post.

        When:
            Instantiated once per bot session.

        How:
            Stores the provided OpenAIClient (or creates one), loads default 
            template corpus, and reads any user-provided custom templates from disk.
        """
        self.openai_client = ai_client
        if not self.openai_client and config.OPENAI_API_KEY:
            self.openai_client = OpenAIClient()
            
        self._default_posts = self._get_default_templates()
        self._custom_posts = self._load_custom_posts(config.CUSTOM_POSTS_FILE)
        
    def _get_default_templates(self):
        """Provide curated default templates across common professional topics.

        Why:
            Ensure the bot still produces sensible content when AI is disabled
            or unavailable.

        When:
            Loaded during initialisation and used as a lookup when topic keywords
            match the template keys.

        How:
            Returns a dictionary mapping topic keywords to prewritten copy.
        """
        return {
            "leadership": "True leadership isn't about being in charge. It's about taking care of those in your charge. Focus on empathy and clear communication today. #Leadership #Management #Growth",
            "productivity": "Efficiency is doing things right; effectiveness is doing the right things. What's one task you can simplify or delegate today? #Productivity #Efficiency #Success",
            "technology": "The best way to predict the future is to create it. How are you leveraging new tech to stay ahead of the curve? #Technology #Innovation #Future",
            "networking": "Your network is your net worth. Take 5 minutes today to reach out to someone you haven't spoken to in a while. #Networking #Community #Career",
            "remote work": "Remote work is not just a trend—it's a fundamental shift in how we think about work and life. Balance is key. #RemoteWork #WorkLifeBalance #FutureOfWork",
            "iot": "Internet of Things (IoT) is connecting the physical and digital worlds in ways we never imagined. Seamless integration is the goal. #IoT #TechTrends #SmartSystems",
            "ai": "Artificial Intelligence is no longer science fiction. It's a tool that can augment human potential when used ethically and thoughtfully. #AI #MachineLearning #Ethics",
            "blockchain": "Trust is at the heart of blockchain technology. Beyond crypto, it's about decentralised verification and security. #Blockchain #Security #Trust",
        }
        
    def _load_custom_posts(self, path):
        """Read user-defined post templates from a local file.

        Why:
            Empower users to use their own voice even when AI is not in use.

        When:
            Executed during object construction.

        How:
            Attempts to open the file at ``path``, reads non-empty lines, and
            logs the result. Returns an empty list if the file is missing or
            malformed.

        Args:
            path (str): File path to load.

        Returns:
            list[str]: Collection of template strings.
        """
        if not path or not Path(path).exists():
            return []
            
        try:
            with open(path, "r") as f:
                lines = [ln.strip() for ln in f.readlines()]
            posts = [ln for ln in lines if ln]
            logging.info(f"Loaded {len(posts)} custom post templates from {path}")
            return posts
        except Exception as e:
            logging.warning(f"Failed to load custom posts from {path}: {e}")
            return []
    
    def _generate_local_post(self, topic, default_post=None):
        """Synthesize a post using templates or randomized phrase fragments.

        Why:
            Maintain automation utility even without networked AI services.

        When:
            Used whenever AI is disabled, misconfigured, or raises an error.

        How:
            Prefers user-provided templates, otherwise combines phrase pools into
            a short narrative and truncates to LinkedIn's character limit.

        Args:
            topic (str): Subject to weave into the post text.
            default_post (str | None): Fallback string if template selection
                fails.

        Returns:
            str: Generated content ready for posting.
        """
        # 1) Use a custom template if available
        if getattr(self, "_custom_posts", None):
            try:
                tpl = random.choice(self._custom_posts)
                text = tpl.format(topic=topic)
                if len(text) > config.MAX_POST_LENGTH:
                    text = text[: config.MAX_POST_LENGTH - 3].rstrip() + "..."
                return self._append_marketing_blurb(text)
            except Exception as e:
                logging.debug(f"Custom template render failed, using randomized: {e}")

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
            "#LeadershipInsights", "#Productivity", "#Tech", "#AI", "#IoT",
            "#DigitalTransformation", "#CareerGrowth", "#Engineering", "#SaaS",
        ]
        intro = random.choice(intros)
        value = random.choice(values)
        action = random.choice(actions)
        hashtags = " ".join(random.sample(hashtags_pool, k=min(3, len(hashtags_pool))))
        post = (
            f"{intro} {topic}.\n\n"
            f"Key principle: {value}.\n\n"
            f"Curious to hear from this community—{action}\n\n"
            f"{hashtags}"
        )
        if len(post) > config.MAX_POST_LENGTH:
            post = post[: config.MAX_POST_LENGTH - 3].rstrip() + "..."
        final_post = post or (default_post or f"Sharing a few thoughts on {topic} today.")
        return self._append_marketing_blurb(final_post)

    def _append_marketing_blurb(self, text: str) -> str:
        """Append a marketing CTA for the open-source project when enabled.

        Why:
            Keeps the bot consistently promoting the linked repository.

        When:
            Called after generating any post content (AI or local fallback).

        How:
            Appends a short CTA with project context and URL unless the text
            already contains the URL or marketing mode is disabled.

        Args:
            text (str): Post content to augment.

        Returns:
            str: Augmented content including the marketing CTA when enabled.
        """
        if not text or not config.MARKETING_MODE:
            return text
        if config.PROJECT_URL in text:
            return text.strip()
        tagline = f"🔗 Explore {config.PROJECT_NAME}: {config.PROJECT_TAGLINE}"
        return f"{text.strip()}\n\n{tagline}"

    def generate_post_content(self, topic: str) -> str:
        """Produce LinkedIn-ready copy for a given topic using OpenAI.

        Why:
            Automate ideation while matching LinkedIn best practices and tone.

        When:
            Called by workflows needing fresh content for a topic run.

        How:
            Attempts to match the topic to a default template, uses OpenAI when
            enabled, and falls back to local generation when AI is unavailable or
            errors occur.

        Args:
            topic (str): The subject matter to write about.

        Returns:
            str: Generated post text including optional marketing blurbs.
        """
        # Pydantic validation (Standard 3)
        try:
            validated = NicheModel(niche=topic or "")
            topic = validated.niche
        except Exception as e:
            logging.error(f"Topic validation failed for generation: {e}")
            raise

        logging.info(f"Generating post content for topic: {topic}")
        
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
        default_post = matched_post or f"Exploring the fascinating world of {topic} today. Innovation and adaptation are key in this rapidly evolving landscape. I'd love to hear your insights on this topic! #ProfessionalDevelopment #IndustryTrends #LinkedIn"
        
        if matched_post:
            logging.info(f"Using matched template for '{matched_key}' keyword in topic: '{topic}'")
        else:
            logging.info(f"Using generic template for topic: '{topic}'")
        
        try:
            if not self.openai_client:
                logging.info("OpenAI client not initialized. Using local fallback content.")
                return self._generate_local_post(topic, default_post)
            
            logging.info("Generating content with OpenAI API...")
            post_text = self.openai_client.generate_post(topic)
            
            if post_text:
                logging.info("Successfully generated post content with OpenAI")
                # OpenAI post generation already includes marketing tail if configured
                return post_text
            
            logging.warning("OpenAI returned empty text, using local fallback content")
            return self._generate_local_post(topic, default_post)
            
        except Exception as e:
            logging.error(f"Failed to generate post content with OpenAI: {str(e)}")
            return self._generate_local_post(topic, default_post)
