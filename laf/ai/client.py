"""OpenAI helpers that turn prompts into LinkedIn posts, comments and calendars.

WHY
  Centralise prompt building and client setup, so every automation flow asks for
  AI content with one call and shares one set of defaults.
"""

import logging
from dataclasses import dataclass
from typing import List, Literal, Optional

from openai import OpenAI, OpenAIError

from laf.ai.prompts import (
    CALENDAR_INSPIRATION_CLAUSE,
    CALENDAR_PERSONAL_STORY_CLAUSE,
    CALENDAR_PROMPT_TEMPLATE,
    CALENDAR_SYSTEM_MESSAGE,
    COMMENT_PERSPECTIVE_INSTRUCTIONS,
    COMMENT_PROMPT_TEMPLATE,
    COMMENT_SYSTEM_MESSAGE,
    POST_PROMPT_TEMPLATE,
    POST_STYLE_TEMPLATES,
    POST_SYSTEM_MESSAGE,
)
from laf.config import CONFIG, Config
from laf.errors import AiError
from laf.text import preprocess_for_ai

logger = logging.getLogger(__name__)

_COMMENT_TONE_NAMES = ("motivational", "thoughtful", "reality_check")

_AUTO_TONE_RULE = (
    "Start your reply with one line in the exact form TONE: <name>, where <name> "
    "is motivational, thoughtful or reality_check. Put the comment on the lines "
    "after it."
)


def _build_auto_perspective_instruction() -> str:
    """List the three tones and ask the model to pick the one that fits.

    WHY
      Auto mode needs the model to see every tone in one prompt, so it can
      choose the right voice in the same call that writes the comment.

    Returns
      str, the three tone texts with a short instruction above them.
    """
    tones = "\n\n".join(
        f"{name}:\n{COMMENT_PERSPECTIVE_INSTRUCTIONS[name]}"
        for name in _COMMENT_TONE_NAMES
    )
    return (
        "Pick the one tone below that best fits this post, then write the "
        f"comment in that tone.\n\n{tones}"
    )


def _parse_tone_reply(text: str) -> tuple[str, str]:
    """Split an auto reply into the comment body and the reported tone.

    WHY
      Auto mode asks the model for a TONE line, so the caller can log the real
      tone. A missing or unknown line must keep the whole reply as the comment
      and report auto instead of dropping text.

    Args
      text: str, the cleaned reply from the model.

    Returns
      tuple[str, str], the comment text and the tone actually used.
    """
    lines = text.splitlines()
    if lines and ":" in lines[0]:
        label, value = lines[0].split(":", 1)
        tone = value.strip().lower()
        if label.strip().lower() == "tone" and tone in _COMMENT_TONE_NAMES:
            body = "\n".join(lines[1:]).strip()
            if body:
                return body, tone
    return text, "auto"


@dataclass
class ContentCalendarRequest:
    """Carry a calendar brief as named fields.

    WHY
      Keep the requested niche, goal, audience and tone in named fields, so the
      prompt builder reads clear values instead of a long argument list.
    """

    niche: str
    goal: str
    audience: str
    tone: str
    content_types: List[str]
    frequency: str
    total_posts: int
    hashtags: List[str]
    inspiration: Optional[str] = None
    personal_story: Optional[str] = None


class OpenAIClient:
    """Wrap the OpenAI client for LinkedIn copy.

    WHY
      Keep prompt templates and model defaults in one place, so post, comment
      and calendar calls share the same setup and tone.
    """

    def __init__(self, config: Config = CONFIG, model: str | None = None) -> None:
        """Build the OpenAI client from the settings for this run.

        WHY
          Read the API key from the injected config, so no client is created at
          import time and a run without a key can still start.

        Args
          config: Config, the settings passed by the caller or the CONFIG default.
          model: Optional[str], the model name override from the caller.

        MUTATIONS
          Stores config, model and client on the instance.
        """
        self.config = config
        self.model = model or self.config.openai_model
        self.client = (
            OpenAI(api_key=self.config.openai_api_key)
            if self.config.openai_api_key
            else None
        )

    def _append_marketing_tail(self, text: str) -> str:
        """Add a promotional tail to generated text.

        WHY
          Keep the project link in AI copy through one rule, so posts and
          comments never add the tail twice or add it when marketing is off.

        Args
          text: str, the generated text from the caller.

        Returns
          str, the text with the tail when marketing mode is on and the project
          URL is missing.
        """
        if not isinstance(text, str):
            return text
        if not text or not self.config.marketing_mode:
            return text.strip()
        if self.config.project_url in text:
            return text.strip()
        tail = (
            f"PS: Check out {self.config.project_name} – {self.config.project_short_pitch} "
            f"{self.config.project_url}"
        )
        return f"{text.strip()} {tail}".strip()

    def generate_post(
        self,
        topic: str,
        style: str = "professional",
        max_tokens: int = 600,
        temperature: float = 0.7,
        summarize_input: bool = True,
    ) -> str:
        """Write a LinkedIn post in the user's voice from a topic.

        WHY
          Give automated topic runs usable copy that matches the user's brand, so
          a run does not need a person to write the post first.

        Args
          topic: str, the subject to write about, from the caller.
          style: str, the template key that shapes the tone.
          max_tokens: int, the token ceiling for the answer.
          temperature: float, the randomness setting for the answer.
          summarize_input: bool, set when a long topic should be shortened first.

        Returns
          str, the generated post text.

        Raises
          AiError: when the client is missing, the call fails, or the answer is
            empty.
        """
        if not self.client:
            raise AiError("AI_UNAVAILABLE")

        if summarize_input and len(topic) > 200:
            topic = preprocess_for_ai(topic, summarize_ratio=0.3, max_chars=200)

        style_instruction = POST_STYLE_TEMPLATES.get(
            style, POST_STYLE_TEMPLATES["professional"]
        )

        prompt = POST_PROMPT_TEMPLATE.format(
            topic=topic,
            style=style,
            style_instruction=style_instruction,
            project_name=self.config.project_name,
            project_pitch=self.config.project_pitch,
            project_url=self.config.project_url,
            project_context=self.config.project_context,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": POST_SYSTEM_MESSAGE},
                    {"role": "user", "content": prompt},
                ],
                temperature=min(temperature, 0.9),
                max_tokens=min(max_tokens, 1000),
                top_p=0.9,
                frequency_penalty=0.3,
                presence_penalty=0.3,
            )
            generated = (response.choices[0].message.content or "").strip()
        except OpenAIError as e:
            logger.error("OpenAI call failed while generating post: %s", e)
            raise AiError("AI_UNAVAILABLE") from e
        except (IndexError, AttributeError) as e:
            logger.error("OpenAI post response had no text: %s", e)
            raise AiError("AI_EMPTY_RESPONSE") from e

        if not generated:
            logger.error("OpenAI returned an empty post")
            raise AiError("AI_EMPTY_RESPONSE")
        return self._append_marketing_tail(generated)

    def generate_comment(
        self,
        post_text: str,
        perspective: Literal["auto", "motivational", "thoughtful", "reality_check"],
        max_tokens: int = 220,
        temperature: float = 0.7,
        summarize_input: bool = True,
    ) -> tuple[str, str]:
        """Write a short LinkedIn comment on a post from a chosen or picked tone.

        WHY
          Give the engage stream a reply that fits the post's tone, so the bot
          can take part in a thread without a person writing each reply.

        Args
          post_text: str, the source post text from the caller.
          perspective: Literal["auto", "motivational", "thoughtful",
            "reality_check"], the tone picked by the caller, or auto to let the
            model pick it.
          max_tokens: int, the token cap for the answer.
          temperature: float, the sampling temperature for the answer.
          summarize_input: bool, set when a long source post should be shortened
            first.

        Returns
          tuple[str, str], the generated comment text and the tone actually used.

        Raises
          AiError: when the client is missing, the call fails, or the answer is
            empty.
          KeyError: when perspective is not one of the supported values.
        """
        if not self.client:
            raise AiError("AI_UNAVAILABLE")

        processed_text = post_text
        if summarize_input and len(post_text) > 300:
            processed_text = preprocess_for_ai(post_text, summarize_ratio=0.3, max_chars=300)

        if perspective == "auto":
            perspective_instruction = _build_auto_perspective_instruction()
            tone_choice_rule = _AUTO_TONE_RULE
        else:
            perspective_instruction = COMMENT_PERSPECTIVE_INSTRUCTIONS[perspective]
            tone_choice_rule = ""

        prompt = COMMENT_PROMPT_TEMPLATE.format(
            post_text=processed_text,
            perspective_instruction=perspective_instruction,
            tone_choice_rule=tone_choice_rule,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": COMMENT_SYSTEM_MESSAGE},
                    {"role": "user", "content": prompt},
                ],
                temperature=min(max(temperature, 0.1), 1.0),  # Clamp between 0.1 and 1.0
                max_tokens=min(max(max_tokens, 20), 300),  # Clamp between 20 and 300 tokens
                top_p=0.9,
                frequency_penalty=0.2,
                presence_penalty=0.2,
            )
            raw_comment = response.choices[0].message.content or ""
        except OpenAIError as e:
            logger.error("OpenAI call failed while generating comment: %s", e)
            raise AiError("AI_UNAVAILABLE") from e
        except (IndexError, AttributeError) as e:
            logger.error("OpenAI comment response had no text: %s", e)
            raise AiError("AI_EMPTY_RESPONSE") from e

        comment = raw_comment.strip()
        comment = comment.replace('\\"', '"').replace("\\'", "'").replace("\\n", "\n")
        comment = comment.strip("\"'").strip()

        if not comment:
            logger.error("OpenAI returned an empty comment")
            raise AiError("AI_EMPTY_RESPONSE")

        if perspective == "auto":
            comment, tone_used = _parse_tone_reply(comment)
        else:
            tone_used = perspective

        logger.info("Generated %s comment with %d characters", tone_used, len(comment))
        return comment, tone_used

    def generate_content_calendar(self, request: ContentCalendarRequest) -> str:
        """Write a multi-day content calendar from a structured brief.

        WHY
          Turn a user's niche, goal and tone into a day-by-day plan, so a
          campaign can be planned without manual drafting.

        Args
          request: ContentCalendarRequest, the brief supplied by the caller.

        Returns
          str, the generated calendar text.

        Raises
          AiError: when the client is missing, the call fails, or the answer is
            empty.
        """

        if not self.client:
            raise AiError("AI_UNAVAILABLE")

        content_types = (
            ", ".join(request.content_types) if request.content_types else "a variety of formats"
        )
        hashtags = (
            ", ".join(f"#{tag.lstrip('#')}" for tag in request.hashtags)
            if request.hashtags
            else "relevant hashtags"
        )
        inspiration = request.inspiration or ""
        personal_story = request.personal_story or ""

        inspiration_clause = (
            CALENDAR_INSPIRATION_CLAUSE.format(inspiration=inspiration)
            if inspiration
            else ""
        )
        personal_clause = (
            CALENDAR_PERSONAL_STORY_CLAUSE.format(personal_story=personal_story)
            if personal_story
            else ""
        )

        prompt = CALENDAR_PROMPT_TEMPLATE.format(
            total_posts=request.total_posts,
            niche=request.niche,
            goal=request.goal,
            audience=request.audience,
            tone=request.tone,
            content_types=content_types,
            frequency=request.frequency,
            hashtags=hashtags,
            inspiration_clause=inspiration_clause,
            personal_clause=personal_clause,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CALENDAR_SYSTEM_MESSAGE},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=min(max(request.total_posts * 80, 600), 3000),
                top_p=0.9,
                frequency_penalty=0.2,
                presence_penalty=0.2,
            )
            calendar_text = (response.choices[0].message.content or "").strip()
        except OpenAIError as exc:
            logger.error("OpenAI call failed while generating calendar: %s", exc)
            raise AiError("AI_UNAVAILABLE") from exc
        except (IndexError, AttributeError) as exc:
            logger.error("OpenAI calendar response had no text: %s", exc)
            raise AiError("AI_EMPTY_RESPONSE") from exc

        if not calendar_text:
            logger.error("OpenAI returned an empty calendar")
            raise AiError("AI_EMPTY_RESPONSE")
        logger.info("Generated content calendar with %d characters", len(calendar_text))
        return calendar_text
