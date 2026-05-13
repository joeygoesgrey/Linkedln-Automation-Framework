"""Pydantic models for LinkedIn automation data validation.

Why:
    Standardise input validation and provide clear interfaces for automation
    tasks like posting, engagement, and profile pursuit.

When:
    Used by CLI entrypoints and LinkedInBot methods to validate arguments
    before executing browser actions.

How:
    Defines models inheriting from pydantic.BaseModel with type hints and
    field-level validation rules.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, validator, HttpUrl

class PostModel(BaseModel):
    """Validation model for individual LinkedIn posts."""
    post_text: str = Field(..., min_length=1, max_length=3000)
    image_directory: Optional[str] = None
    image_paths: Optional[List[str]] = None
    schedule_date: Optional[str] = None
    schedule_time: Optional[str] = None
    no_images: bool = False

class TopicsModel(BaseModel):
    """Validation model for bulk topic processing."""
    topic_file_path: str
    image_directory: Optional[str] = None
    schedule_date: Optional[str] = None
    schedule_time: Optional[str] = None
    engage_with_feed: bool = False
    max_posts_to_engage: int = Field(default=3, ge=0)
    perspectives: Optional[List[str]] = None
    no_images: bool = False

class EngageModel(BaseModel):
    """Validation model for feed engagement tasks."""
    mode: Literal["like", "comment", "both"] = "both"
    max_actions: int = Field(default=10, ge=1)

class PursueModel(BaseModel):
    """Validation model for target profile engagement."""
    profile_name: str = Field(..., min_length=1)
    max_posts: int = Field(default=5, ge=0)
    should_follow: bool = True
    should_like: bool = True
    should_comment: bool = True
    comment_perspectives: Optional[List[str]] = None
    bio_keywords: Optional[List[str]] = None

class CalendarModel(BaseModel):
    """Validation model for content calendar generation."""
    niche: str = Field(..., min_length=1)
    output_file: str = "calendar.txt"
    total_posts: int = Field(default=30, gt=0)

class RepostModel(BaseModel):
    """Validation model for reposting content."""
    thoughts_text: Optional[str] = None
    mention_author: bool = True
    mention_position: Literal["prepend", "append"] = "prepend"

class LoginModel(BaseModel):
    """Validation model for LinkedIn credentials."""
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)

class NicheModel(BaseModel):
    """Validation model for industry niche descriptions."""
    niche: str = Field(..., min_length=1, max_length=100)
