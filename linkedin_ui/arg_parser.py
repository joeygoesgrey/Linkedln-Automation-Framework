# linkedin_ui/arg_parser.py
import argparse
from typing import Optional, List, Dict, Any

def setup_argument_parser() -> argparse.ArgumentParser:
    """Construct and configure the bot's CLI argument parser.

    Returns:
        argparse.ArgumentParser: Parser populated with all command line options
    """
    parser = argparse.ArgumentParser(
        description="LinkedIn automation bot for posting content and engagement.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    subparsers.required = True
    
    # Post command (default)
    post_parser = subparsers.add_parser('post', help='Post content to LinkedIn')
    _setup_post_parser(post_parser)
    
    # Generate calendar command
    calendar_parser = subparsers.add_parser('generate-calendar', help='Generate a content calendar')
    _setup_calendar_parser(calendar_parser)
    
    # Engage command
    engage_parser = subparsers.add_parser('engage', help='Engage with your feed')
    _setup_engage_parser(engage_parser)
    
    # New: Pursue command
    pursue_parser = subparsers.add_parser('pursue', help='Pursue and engage with a specific person\'s profile')
    _setup_pursue_parser(pursue_parser)

    # New: Repost command
    repost_parser = subparsers.add_parser('repost', help='Repost the first post on the feed with your thoughts')
    _setup_repost_parser(repost_parser)
    
    # Add common arguments
    for p in [post_parser, calendar_parser, engage_parser, pursue_parser, repost_parser]:
        p.add_argument('--debug', action='store_true', help='Enable debug logging')
        p.add_argument('--headless', action='store_true', help='Run browser in headless mode')
        p.add_argument('--no-ai', action='store_true', help='Disable AI generation')
    
    return parser

def _setup_post_parser(parser: argparse.ArgumentParser) -> None:
    """Set up arguments for the 'post' command."""
    parser.add_argument(
        "--topics-file", 
        default="topics.txt",
        help="Path to a text file containing post topics, one per line."
    )
    parser.add_argument(
        "--text",
        help="Specific text to post immediately (overrides topics file)."
    )
    parser.add_argument(
        "--images-dir", 
        default=None,
        help="Path to a directory containing images to use for posts."
    )
    parser.add_argument(
        "--no-images", 
        action="store_true",
        help="Disable image uploads even if --images-dir is provided."
    )
    parser.add_argument(
        "--schedule-date",
        default=None,
        help="Schedule date in mm/dd/yyyy."
    )
    parser.add_argument(
        "--schedule-time",
        default=None,
        help="Schedule time (e.g., '10:45 AM')."
    )

def _setup_calendar_parser(parser: argparse.ArgumentParser) -> None:
    """Set up arguments for the 'generate-calendar' command."""
    parser.add_argument(
        "--output",
        default="content_calendar.txt",
        help="Output file for the generated calendar."
    )
    parser.add_argument(
        "--niche",
        required=True,
        help="Industry or niche for the content calendar (e.g., fitness, SaaS)."
    )
    parser.add_argument(
        "--total-posts",
        type=int,
        default=30,
        help="Total number of posts to generate."
    )

def _setup_engage_parser(parser: argparse.ArgumentParser) -> None:
    """Set up arguments for the 'engage' command."""
    parser.add_argument(
        "--action",
        choices=["like", "comment", "both"],
        default="both",
        help="Type of engagement to perform."
    )
    parser.add_argument(
        "--max-actions",
        type=int,
        default=10,
        help="Maximum number of posts to engage with."
    )

def _setup_pursue_parser(parser: argparse.ArgumentParser) -> None:
    """Set up arguments for the 'pursue' command."""
    parser.add_argument(
        "profile_name",
        help="Name of the person to engage with"
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=5,
        help="Maximum number of posts to engage with"
    )
    parser.add_argument(
        "--no-follow",
        action="store_false",
        dest="should_follow",
        help="Skip following the profile"
    )
    parser.add_argument(
        "--no-like",
        action="store_false",
        dest="should_like",
        help="Skip liking posts"
    )
    parser.add_argument(
        "--no-comment",
        action="store_false",
        dest="should_comment",
        help="Skip commenting on posts"
    )
    parser.add_argument(
        "--perspectives",
        nargs="+",
        default=["insightful", "funny", "motivational"],
        help="AI comment perspectives to use"
    )
    parser.add_argument(
        "--bio-keywords", 
        nargs="+", 
        default=None,
        help="List of keywords to look for in the profile bio"
    )

def _setup_repost_parser(parser: argparse.ArgumentParser) -> None:
    """Set up arguments for the 'repost' command."""
    parser.add_argument(
        "--thoughts",
        default=None,
        help="Your thoughts to accompany the repost. If omitted, AI will generate them."
    )
    parser.add_argument(
        "--mention-author",
        action="store_true",
        help="Mention the original author in your repost thoughts."
    )
    parser.add_argument(
        "--mention-position",
        choices=["prepend", "append"],
        default="append",
        help="Where to place the author mention in the text."
    )