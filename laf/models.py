"""Pydantic models for LinkedIn automation data validation.

WHY
  Standardise input validation and give every automation task one typed model,
  so bad arguments fail before any browser action runs.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class PostModel(BaseModel):
    """Validation model for individual LinkedIn posts.

    WHY
      Check one post's text length and optional media and schedule values
      before any browser action runs.

    Raises
      pydantic.ValidationError: when a field fails a type or length constraint.
    """

    post_text: str = Field(..., min_length=1, max_length=3000)
    image_directory: Optional[str] = None
    image_paths: Optional[List[str]] = None
    schedule_date: Optional[str] = None
    schedule_time: Optional[str] = None
    no_images: bool = False


class TopicsModel(BaseModel):
    """Validation model for bulk topic processing.

    WHY
      Check one bulk topic run's file path, engagement limit and options
      before the browser is touched.

    Raises
      pydantic.ValidationError: when a field fails a type or range constraint.
    """

    topic_file_path: str
    image_directory: Optional[str] = None
    schedule_date: Optional[str] = None
    schedule_time: Optional[str] = None
    engage_with_feed: bool = False
    max_posts_to_engage: int = Field(default=3, ge=0)
    perspectives: Optional[List[str]] = None
    no_images: bool = False


class EngageModel(BaseModel):
    """Validation model for feed engagement tasks.

    WHY
      Check the engagement mode and action limit before the feed flow starts.

    Raises
      pydantic.ValidationError: when the mode or the action limit is invalid.
    """

    mode: Literal["like", "comment", "both"] = "both"
    max_actions: int = Field(default=10, ge=1)


class PursueModel(BaseModel):
    """Validation model for target profile engagement.

    WHY
      Check the target name, post limit and follow, like and comment flags
      before a profile flow starts.

    Raises
      pydantic.ValidationError: when a field fails a type or range constraint.
    """

    profile_name: str = Field(..., min_length=1)
    max_posts: int = Field(default=5, ge=0)
    should_follow: bool = True
    should_like: bool = True
    should_comment: bool = True
    comment_perspectives: Optional[List[str]] = None
    bio_keywords: Optional[List[str]] = None


class CalendarModel(BaseModel):
    """Validation model for content calendar generation.

    WHY
      Check the niche, output file and post count before the AI calendar call
      runs.

    Raises
      pydantic.ValidationError: when a field fails a type or range constraint.
    """

    niche: str = Field(..., min_length=1)
    output_file: str = "calendar.txt"
    total_posts: int = Field(default=30, gt=0)


class RepostModel(BaseModel):
    """Validation model for reposting content.

    WHY
      Check the repost thoughts and mention options before the repost flow
      starts.

    Raises
      pydantic.ValidationError: when the mention position is not prepend or
        append.
    """

    thoughts_text: Optional[str] = None
    mention_author: bool = True
    mention_position: Literal["prepend", "append"] = "prepend"


class LoginModel(BaseModel):
    """Validation model for LinkedIn credentials.

    WHY
      Check the username and password lengths before a login attempt reaches
      the browser.

    Raises
      pydantic.ValidationError: when a credential is shorter than its minimum.
    """

    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class NicheModel(BaseModel):
    """Validation model for industry niche descriptions.

    WHY
      Check a niche string's length before it is used to build AI prompts.

    Raises
      pydantic.ValidationError: when the niche is empty or longer than 100
        characters.
    """

    niche: str = Field(..., min_length=1, max_length=100)
