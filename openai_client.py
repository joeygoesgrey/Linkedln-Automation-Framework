"""OpenAI-powered helpers for LinkedIn post, comment, and calendar generation.

Why:
    Centralise prompt engineering and client management so automation flows can
    request AI content with one-liners.

When:
    Imported by the bot during initialisation when an ``OPENAI_API_KEY`` exists.

How:
    Instantiates a shared :class:`openai.OpenAI` client, defines request payloads,
    and exposes convenience methods for posts, comments, and content calendars.
"""

import logging
from dataclasses import dataclass
from typing import List, Literal, Optional
from openai import OpenAI

import config
from config import OPENAI_API_KEY, OPENAI_MODEL
from text_utils import preprocess_for_ai

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


@dataclass
class ContentCalendarRequest:
    """Structured payload describing a desired LinkedIn content calendar.

    Why:
        Prompts benefit from explicit field separation, and dataclasses provide
        validation-friendly containers.

    When:
        Constructed by CLI handlers before calling
        :meth:`OpenAIClient.generate_content_calendar`.

    How:
        Stores descriptive metadata such as niche, goal, audience, tone, and
        optional inspiration fields used to craft the AI prompt.
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
    """Wrapper around the OpenAI client tailored for LinkedIn content.

    Why:
        Encapsulate prompt templates and client defaults, reducing duplication.

    When:
        Instantiated by :class:`LinkedInBot` whenever OpenAI credentials are
        available.

    How:
        Holds a reference to the shared :class:`OpenAI` client, stores style
        templates, and exposes methods to craft posts, comments, and calendars.
    """

    def __init__(self, model: str = OPENAI_MODEL) -> None:
        """Initialise the wrapper with a preferred OpenAI model.

        Why:
            Allow callers to override model aliases (e.g., for testing or cost
            control) without altering code elsewhere.

        When:
            Called during bot construction.

        How:
            Stores the chosen model name, references the shared client, and
            prepares reusable style templates used by :meth:`generate_post`.

        Args:
            model (str): Name or alias of the OpenAI chat completion model to use.
        """
        self.model = model
        self.client = client

        # Style templates to add variation
        self.style_templates: dict[str, str] = {
            "professional": "Write with clarity, authority, and professionalism.",
            "storytelling": "Start with a short, engaging story or anecdote before the main lesson.",
            "listicle": "Present the content as 3–5 quick, punchy lessons or tips.",
            "contrarian": "Open with a bold or controversial opinion, then explain why.",
            "funny": "Use light humor, analogies, or playful tone to explain the idea.",
            "inspirational": "Be motivational and uplifting, focusing on big-picture impact."
        }

    def _append_marketing_tail(self, text: str) -> str:
        """Append a promotional tail encouraging readers to explore the project.

        Args:
            text (str): Generated OpenAI text (post, comment, or fallback).

        Returns:
            str: Text with a promotional tail when marketing mode is enabled.
        """
        if not isinstance(text, str):
            return text
        if not text or not config.MARKETING_MODE:
            return text.strip()
        if config.PROJECT_URL in text:
            return text.strip()
        tail = f"PS: Check out {config.PROJECT_NAME} – {config.PROJECT_SHORT_PITCH} {config.PROJECT_URL}"
        return f"{text.strip()} {tail}".strip()

    def generate_post(
        self,
        topic: str,
        style: str = "professional",
        max_tokens: int = 600,
        temperature: float = 0.7,
        summarize_input: bool = True
    ) -> str:
        """Produce a LinkedIn post in Joseph's voice using OpenAI.

        Why:
            Provide high-quality, structured posts tailored to the user's brand.

        When:
            Called when automated topic runs use OpenAI or local templates.

        How:
            Optionally summarises long topics, selects a style template, crafts a
            structured prompt, and requests a chat completion.

        Args:
            topic (str): Subject matter to cover.
            style (str): Style template key controlling prompt flavour.
            max_tokens (int): Token ceiling for the generated response.
            temperature (float): Randomness setting for the completion.
            summarize_input (bool): Whether to normalise lengthy topics first.

        Returns:
            str: Generated LinkedIn post content.

        Raises:
            ValueError: If the OpenAI client is not initialised.
            Exception: Propagates API errors for upstream handling.
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized. Please set OPENAI_API_KEY in .env")

        if summarize_input and len(topic) > 200:
            topic = preprocess_for_ai(topic, summarize_ratio=0.3, max_chars=200)

        style_instruction = self.style_templates.get(style, self.style_templates["professional"])

        PROMPT_TEMPLATE = """
You are Joseph Edomobi (joeygoesgrey), a Nigerian full-stack developer and entrepreneur.
Write a LinkedIn post about "{topic}" in a {style} style.

Project context you should weave in naturally:
{project_context}

Follow this structure:
1. **Hook** → A bold, curiosity-driven first line (e.g., "How I...", "How to... without...", "Imagine if...").
2. **Story** → Use a mini-story or analogy. Show a problem → journey → resolution.
3. **Lesson** → Share the insight or key takeaway in simple, clear language.
4. **Engagement Question** → End with a contextual question (not generic).
5. **Hashtags** → Add 3–5 strong, relevant hashtags.
6. **Image Suggestion** → Recommend what kind of image fits the post (before/after, selfie, infographic, etc.).

Rules:
- Write at a 6th–7th grade reading level.
- Short sentences. No jargon.
- Conversational tone. Sound human, not corporate.
- Keep it under 300 words.
- Use emojis naturally and where necessary to make it visually appealing.
- Hashtags should not be generic like #JoinTheRevolution. Prefer niche tags (e.g., #AIinHealthcare).
- Include a friendly CTA inviting readers to explore {project_name}, the open-source toolkit that {project_pitch}. Add the link {project_url} near the end without sounding spammy.

{style_instruction}
"""
        prompt = PROMPT_TEMPLATE.format(
            topic=topic,
            style=style,
            style_instruction=style_instruction,
            project_name=config.PROJECT_NAME,
            project_pitch=config.PROJECT_PITCH,
            project_url=config.PROJECT_URL,
            project_context=config.PROJECT_CONTEXT,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a LinkedIn growth strategist who writes engaging, human-like posts."},
                    {"role": "user", "content": prompt}
                ],
                temperature=min(temperature, 0.9),
                max_tokens=min(max_tokens, 1000),
                top_p=0.9,
                frequency_penalty=0.3,
                presence_penalty=0.3
            )
            generated = response.choices[0].message.content.strip()
            return self._append_marketing_tail(generated)
        except Exception as e:
            logging.error(f"Error generating post with OpenAI: {str(e)}")
            raise

    def generate_comment(
        self,
        post_text: str,
        perspective: Literal["funny", "motivational", "insightful"],
        max_tokens: int = 150,
        temperature: float = 0.7,
        summarize_input: bool = True
    ) -> str:
        """Draft a conversational LinkedIn comment from a given perspective.

        Why:
            Engagement loops need authentic-sounding replies tailored to the
            post's tone.

        When:
            Called by the engage stream whenever AI commenting is enabled.

        How:
            Optionally summarises long posts, selects a perspective-specific
            instruction, and requests a concise chat completion.

        Args:
            post_text (str): Source post content.
            perspective (Literal["funny", "motivational", "insightful"]): Desired
                tone for the reply.
            max_tokens (int): Token cap for the response.
            temperature (float): Sampling temperature passed to OpenAI.
            summarize_input (bool): Whether to trim long source posts.

        Returns:
            str: Generated comment, or a fallback message when errors occur.

        Raises:
            ValueError: If the OpenAI client is missing.
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized. Please set OPENAI_API_KEY in .env")

        perspective_map: dict[str, str] = {
            "funny": "Add a witty, light-hearted take on the post. Keep it professional but funny. Include one well-placed emoji if it heightens the punchline.",
            "motivational": "Provide encouragement and uplifting perspective. Be inspiring. Add a single emoji that reinforces the encouragement.",
            "insightful": "Give a thoughtful comment that adds unique value to the discussion. Share a unique insight or perspective. You may finish with a subtle emoji that signals appreciation or curiosity."
        }

        processed_text = post_text
        if summarize_input and len(post_text) > 300:
            processed_text = preprocess_for_ai(
                post_text,
                summarize_ratio=0.3,
                max_chars=300
            )

        COMMENT_PROMPT_TEMPLATE = """Write a LinkedIn comment in response to this post.

Post content:
{post_text}

Project context you can reference:
{project_context}

Guidelines:
- Tone: {perspective_instruction}
- Length: 1-2 concise sentences
- Style: Natural, conversational, and professional
- Use emojis naturally and where necessary to make it visually appealing (1-2 max)
- No quotes
- Sound like a real human, not AI-generated
- Add value to the conversation
- Be specific and relevant to the post
- After addressing the post, include a short CTA inviting readers to explore {project_name}, {project_short_pitch} ({project_url}). Keep it friendly and under 20 words.

Comment:"""
        prompt = COMMENT_PROMPT_TEMPLATE.format(
            post_text=processed_text,
            perspective_instruction=perspective_map[perspective],
            project_name=config.PROJECT_NAME,
            project_short_pitch=config.PROJECT_SHORT_PITCH,
            project_url=config.PROJECT_URL,
            project_context=config.PROJECT_CONTEXT,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Joseph Edomobi, a Nigerian full-stack developer and entrepreneur. "
                            "You write authentic, engaging LinkedIn comments that add value to the conversation."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=min(max(temperature, 0.1), 1.0),  # Clamp between 0.1 and 1.0
                max_tokens=min(max(max_tokens, 20), 300),    # Clamp between 20 and 300 tokens
                top_p=0.9,
                frequency_penalty=0.2,
                presence_penalty=0.2
            )

            comment = response.choices[0].message.content.strip()
            comment = comment.replace('\\"', '"').replace("\\'", "'").replace('\\n', '\n')
            comment = comment.strip('"\'').strip()

            if comment:
                comment = self._append_marketing_tail(comment)
            else:
                comment = self._append_marketing_tail("Great post! Thanks for sharing.")

            logging.info(f"Generated {perspective} comment with {len(comment)} characters")

            return comment

        except Exception as e:
            logging.error(f"Error generating comment: {e}")
            return self._append_marketing_tail("Great post! Thanks for sharing.")

    def generate_content_calendar(self, request: ContentCalendarRequest) -> str:
        """Draft a LinkedIn content calendar based on user-supplied goals.

        Why:
            Help users plan multi-day content campaigns without manual drafting.

        When:
            Invoked by the CLI ``--generate-calendar`` workflow.

        How:
            Builds a detailed prompt describing niche, goals, tone, and optional
            inspiration, then requests a chat completion that emits day-by-day
            ideas.

        Args:
            request (ContentCalendarRequest): Structured description of the
                desired calendar.

        Returns:
            str: AI-generated calendar text.

        Raises:
            ValueError: If the OpenAI client is not initialised.
            Exception: Propagates API errors for caller handling.
        """

        if not self.client:
            raise ValueError("OpenAI client not initialized. Please set OPENAI_API_KEY in .env")

        content_types = ", ".join(request.content_types) if request.content_types else "a variety of formats"
        hashtags = ", ".join(f"#{tag.lstrip('#')}" for tag in request.hashtags) if request.hashtags else "relevant hashtags"
        inspiration = request.inspiration or ""
        personal_story = request.personal_story or ""

        inspiration_clause = (
            f"- The user admires or draws inspiration from {inspiration}.\n" if inspiration else ""
        )
        personal_clause = (
            f"- The user wants to weave in personal stories such as: {personal_story}.\n" if personal_story else ""
        )

        prompt = f"""
I need help generating a {request.total_posts}-day content plan for the {request.niche} niche.
The user wants to focus on {request.goal} and their target audience is {request.audience}.
The content should be written in a {request.tone} tone. Posts should emphasise {content_types}.
Please follow these guidelines:
- Posting frequency: {request.frequency}
- Use these hashtags or keywords throughout: {hashtags}
{inspiration_clause}{personal_clause}
Output {request.total_posts} unique post ideas. For each idea, produce a single line in the format:
Day X | Hook | Content Description | Suggested CTA | Suggested hashtags
Hooks should be catchy, descriptions concise (one to two sentences), CTA actionable, and hashtags relevant.
Avoid duplicate ideas and keep the tone consistent with the brief.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert LinkedIn content strategist who creates month-long content calendars "
                            "with concise, actionable ideas."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=min(max(request.total_posts * 80, 600), 3000),
                top_p=0.9,
                frequency_penalty=0.2,
                presence_penalty=0.2,
            )
            calendar_text = response.choices[0].message.content.strip()
            logging.info(
                "Generated content calendar with %d characters", len(calendar_text)
            )
            return calendar_text
        except Exception as exc:
            logging.error(f"Error generating content calendar: {exc}")
            raise
