#!/usr/bin/env python3
"""LinkedIn bot command-line entry point.

Why:
    Consolidate posting, scheduling, image attachment, engagement, and
    calendar-generation flows into a single executable interface.

When:
    Run directly via ``python main.py`` or import :func:`main` from other tooling
    that must drive the automation pipeline programmatically.

How:
    Defines the CLI parser, configures logging/runtime switches, instantiates
    :class:`LinkedInBot`, and dispatches to the requested workflow before
    returning an exit status.
"""
import sys
import logging
import json
import config
from linkedin_ui.arg_parser import setup_argument_parser
from linkedin_bot import LinkedInBot

def setup_logging(debug: bool = False) -> None:
    """Configure logging based on debug flag.

    Args:
        debug (bool): If True, set logging level to DEBUG. Otherwise INFO.

    Returns:
        None

    Raises:
        TypeError: If debug is not a boolean.
    """
    # Standard 3: Validation logic at start
    if not isinstance(debug, bool):
        raise TypeError(f"debug must be a boolean, got {type(debug)}")

    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

def main() -> int:
    """Main entry point for the LinkedIn bot.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    try:
        # Parse command line arguments
        parser = setup_argument_parser()
        if parser is None:
            logging.error("Failed to initialize argument parser.")
            return 1

        args = parser.parse_args()
        
        # Standard 3: Basic validation
        if not hasattr(args, 'command') or args.command is None:
            logging.error("No command provided.")
            return 1

        # Configure logging
        setup_logging(debug=getattr(args, 'debug', False))

        # Initialize the bot
        bot = LinkedInBot(use_openai=not getattr(args, 'no_ai', False))
        if getattr(args, 'headless', False):
            # If headless mode is needed, we'll set it in the config
            config.HEADLESS = True

        # Standard 3: Basic validation using Pydantic models
        from models import PostModel, CalendarModel, EngageModel, PursueModel, RepostModel
        
        # Dispatch to the appropriate command handler
        if args.command == 'post':
            # Handle post command
            try:
                validated = PostModel(
                    post_text=getattr(args, 'text', '') or '',
                    image_directory=args.images_dir,
                    schedule_date=args.schedule_date,
                    schedule_time=args.schedule_time,
                    no_images=args.no_images
                )
            except Exception as e:
                logging.error(f"Post validation failed: {e}")
                return 1

            if getattr(args, 'text', None):
                bot.post_custom_text(
                    post_text=validated.post_text,
                    image_directory=validated.image_directory,
                    schedule_date=validated.schedule_date,
                    schedule_time=validated.schedule_time,
                    no_images=validated.no_images
                )
            else:
                bot.process_topics(
                    topic_file_path=args.topics_file,
                    image_directory=validated.image_directory,
                    schedule_date=validated.schedule_date,
                    schedule_time=validated.schedule_time,
                    no_images=validated.no_images
                )
            
        elif args.command == 'generate-calendar':
            # Handle calendar generation
            try:
                validated = CalendarModel(
                    niche=args.niche,
                    output_file=args.output,
                    total_posts=args.total_posts
                )
            except Exception as e:
                logging.error(f"Calendar validation failed: {e}")
                return 1

            bot.generate_content_calendar(
                niche=validated.niche,
                output_file=validated.output_file,
                total_posts=validated.total_posts
            )
            
        elif args.command == 'engage':
            # Handle engagement
            try:
                validated = EngageModel(
                    mode=args.action,
                    max_actions=args.max_actions
                )
            except Exception as e:
                logging.error(f"Engagement validation failed: {e}")
                return 1

            if not bot.linkedin.login():
                logging.error("Failed to login to LinkedIn.")
                return 1
            success = bot.linkedin.engage_stream(
                mode=validated.mode,
                max_actions=validated.max_actions,
                ai_client=bot.openai_client,
                post_extractor=bot.post_extractor
            )
            logging.info(f"Engagement stream completed: {'Success' if success else 'Failed'}")
            
        elif args.command == 'pursue':
            # Handle pursue command
            try:
                validated = PursueModel(
                    profile_name=args.profile_name,
                    max_posts=args.max_posts,
                    should_follow=args.should_follow,
                    should_like=args.should_like,
                    should_comment=args.should_comment,
                    comment_perspectives=args.perspectives,
                    bio_keywords=args.bio_keywords
                )
            except Exception as e:
                logging.error(f"Pursue validation failed: {e}")
                return 1

            results = bot.pursue_investor(
                profile_name=validated.profile_name,
                max_posts=validated.max_posts,
                should_follow=validated.should_follow,
                should_like=validated.should_like,
                should_comment=validated.should_comment,
                comment_perspectives=validated.comment_perspectives,
                bio_keywords=validated.bio_keywords
            )
            logging.info(f"Pursuit results: {json.dumps(results, indent=2)}")
            return 0 if not results.get('errors') else 1

        elif args.command == 'repost':
            # Handle repost command
            try:
                validated = RepostModel(
                    thoughts_text=args.thoughts,
                    mention_author=args.mention_author,
                    mention_position=args.mention_position
                )
            except Exception as e:
                logging.error(f"Repost validation failed: {e}")
                return 1

            if not bot.linkedin.login():
                logging.error("Failed to login to LinkedIn.")
                return 1
                
            comment_generator = None
            if not validated.thoughts_text and not args.no_ai:
                def build_repost_thoughts(post_root):
                    base_text = "Great insights! Had to share this."
                    if bot.openai_client:
                        try:
                            post_text = bot.post_extractor.extract_text(post_root)
                        except Exception:
                            post_text = ""
                        if post_text:
                            try:
                                return bot.openai_client.generate_comment(
                                    post_text=post_text,
                                    perspective="insightful",
                                    max_tokens=180,
                                    temperature=0.7,
                                )
                            except Exception as err:
                                logging.error(f"AI repost thoughts generation failed: {err}")
                    return base_text
                comment_generator = build_repost_thoughts
                
            success = bot.linkedin.repost_first_post(
                thoughts_text=validated.thoughts_text,
                comment_generator=comment_generator,
                mention_author=validated.mention_author,
                mention_position=validated.mention_position
            )
            if success:
                logging.info("Successfully reposted the first post on the feed.")
                return 0
            else:
                logging.error("Failed to repost the first post.")
                return 1

        # Close the bot resources
        bot.close()
        logging.info("LinkedIn Bot completed successfully")
        return 0
        
    except Exception as e:
        logging.error(f"LinkedIn Bot encountered an error: {str(e)}", exc_info=True)
        return 1
    finally:
        if 'bot' in locals():
            try:
                bot.close()
            except:
                pass

if __name__ == "__main__":
    sys.exit(main())
