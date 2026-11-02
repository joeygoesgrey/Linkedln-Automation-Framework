"""Named error classes that carry a code and data, with no user facing text."""


class LAFError(Exception):
    """Base error for every failure the bot reports to the user.

    WHY
        One base type lets the command line catch every expected failure while
        the error object stays free of user facing sentences.
    """

    def __init__(self, code: str, **fields: object) -> None:
        """Build an error that carries a code and its field data.

        WHY
            A plain exception string cannot be matched reliably and carries no
            data for the message templates.

        Args
            code: uppercase area code that also names the message template.
            fields: keyword data used by the message templates.

        Raises
            TypeError: when code is not a string.

        MUTATIONS
            write: stores the code and the field data on the instance.
        """
        if not isinstance(code, str):
            raise TypeError("code must be a string")
        super().__init__(code)
        self.code: str = code
        self.fields: dict[str, object] = dict(fields)

    def __str__(self) -> str:
        """Return the code as the short form of this error.

        WHY
            Logs and the command line need one stable token, not a Python
            repr full of field values.

        Returns
            str: the error code.
        """
        return self.code


class LoginError(LAFError):
    """Failure while signing in to LinkedIn.

    WHY
        Groups every sign in failure under one type so the command line can
        handle login problems without catching every LAFError.
    """


class ComposerError(LAFError):
    """Failure while opening the post composer.

    WHY
        Keeps composer failures separate from posting failures so the caller
        knows the editor never became ready.
    """


class PostError(LAFError):
    """Failure while publishing a post.

    WHY
        Keeps text post failures separate from composer and media failures so
        the caller can report the exact step that broke.
    """


class MediaError(LAFError):
    """Failure while attaching images to a post.

    WHY
        Groups folder, file and upload failures under one type so image checks
        are handled in one place.
    """


class ScheduleError(LAFError):
    """Failure while scheduling a post.

    WHY
        Separates date, time and control failures so the user can fix the exact
        value that was wrong.
    """


class TopicsError(LAFError):
    """Failure while reading a topics file.

    WHY
        Keeps file problems separate from posting problems so a missing or
        empty file is reported before any browser work starts.
    """


class FeedError(LAFError):
    """Failure while loading or reading the feed.

    WHY
        Groups feed loading and feed button failures so the engage flow can
        stop early with one clear reason.
    """


class CommentError(LAFError):
    """Failure while writing a comment.

    WHY
        Keeps comment box, text and submit failures apart from like failures
        so the engage flow can report the right step.
    """


class RepostError(LAFError):
    """Failure while reposting a post with thoughts.

    WHY
        Groups menu, option, text and share failures so the repost flow can
        name the exact control that did not appear.
    """


class EngageError(LAFError):
    """Failure while running actions over a post.

    WHY
        Separates per post engagement failures from feed and comment failures
        so a batch can skip one post and keep going.
    """


class ProfileError(LAFError):
    """Failure while pursuing a profile.

    WHY
        Groups profile lookup, follow and post failures so the pursue flow has
        one type to handle.
    """


class CalendarError(LAFError):
    """Failure while writing a content calendar.

    WHY
        Keeps calendar file failures separate from AI failures so the user
        knows whether the content or the disk was the problem.
    """


class AiError(LAFError):
    """Failure while generating text with an AI model.

    WHY
        Groups unavailable model and empty answer failures so content flows can
        stop with one type.
    """


class MentionError(LAFError):
    """Failure while inserting a mention into a post.

    WHY
        Separates typeahead, match and confirm failures so the composer can
        tell the user which part of the mention went wrong.
    """


class VerifyError(LAFError):
    """Failure while checking that a post was published.

    WHY
        Keeps verification failures separate from posting failures so a silent
        LinkedIn error does not look like a successful post.
    """


class ConfigError(LAFError):
    """Failure while reading configuration values.

    WHY
        Keeps bad environment values separate from browser and network
        failures so the user can fix the file they control.
    """


class DriverError(LAFError):
    """Failure while starting or talking to the browser driver.

    WHY
        Groups browser startup failures so main.py can catch one type and skip
        a long Selenium trace.
    """
