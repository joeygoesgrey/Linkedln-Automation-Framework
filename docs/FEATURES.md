# Features

This file records what the bot is meant to do, in plain words. It is the
checklist used by tests and by `tools/check_selectors.py`.

Rules for this file:

- It records intended behaviour, not current behaviour.
- Every feature has an ID. Tests name their feature ID.
- When a selector check fails, the feature ID says what broke.
- Error codes are final and live in `laf/messages.py`. Every code has a row in
  the README Troubleshooting table.

## F01 Log in

- Command: any command.
- Input: `LINKEDIN_USERNAME` and `LINKEDIN_PASSWORD` in `.env`.
- Success: the feed URL loads and the account name is visible.
- Failure: missing credentials, wrong credentials, network error, captcha.
- Codes: `LOGIN_CREDENTIALS_MISSING`, `LOGIN_REJECTED`, `LOGIN_TIMEOUT`.

## F02 Pass two-factor verification

- Command: any command, when LinkedIn asks for a code.
- Input: the code typed by the user in the terminal.
- Success: login continues and the feed loads.
- Failure: no code provided, wrong code, prompt timed out.
- Codes: `LOGIN_2FA_MISSING`, `LOGIN_2FA_REJECTED`.

## F03 Publish a text post

- Command: `python main.py post --text "..."`
- Input: post text from the command line.
- Success: a toast confirms the post and it appears on the profile.
- Failure: composer did not open, Post button not found, text rejected.
- Codes: `COMPOSER_NOT_OPEN`, `COMPOSER_POST_BUTTON_MISSING`, `POST_REJECTED`.

## F04 Publish a post with images

- Command: `python main.py post --text "..." --images-dir ./images`
- Input: a folder of images.
- Success: the images appear in the composer before posting.
- Failure: folder missing, no images inside, file too large, file input not found.
- Codes: `IMAGE_DIR_MISSING`, `IMAGE_NONE_FOUND`, `IMAGE_UPLOAD_FAILED_PATH`, `IMAGE_UPLOAD_FAILED_SIZE`, `IMAGE_UPLOAD_FAILED_FORMAT`.

## F05 Schedule a post

- Command: `python main.py post --text "..." --schedule-date mm/dd/yyyy --schedule-time "10:45 AM"`
- Input: text and a future date and time.
- Success: LinkedIn confirms the scheduled post.
- Failure: bad date format, past date, schedule control missing.
- Codes: `SCHEDULE_DATE_INVALID`, `SCHEDULE_TIME_INVALID`, `SCHEDULE_CONTROL_MISSING`.

## F06 Post from a topics file

- Command: `python main.py post --topics-file topics.txt`
- Input: a text file with one topic per line.
- Success: each unposted topic becomes a post, and the file records what was posted.
- Failure: file missing, file empty, all topics already posted.
- Codes: `TOPICS_FILE_MISSING`, `TOPICS_FILE_EMPTY`, `TOPICS_NONE_REMAINING`.

## F07 Like the first feed post

- Command: `python main.py engage --action like`
- Input: a loaded feed.
- Success: the Like button shows the pressed state.
- Failure: feed did not load, action bar missing, button not found.
- Codes: `FEED_LOAD_FAILED`, `FEED_ACTION_BAR_MISSING`, `LIKE_BUTTON_MISSING`.

## F08 Comment on the first feed post

- Command: `python main.py engage --action comment`
- Input: a loaded feed and comment text, or an AI generator.
- Success: the comment appears under the post.
- Failure: feed did not load, comment box missing, empty comment text, submit button missing.
- Codes: `FEED_LOAD_FAILED`, `COMMENT_BOX_MISSING`, `COMMENT_TEXT_EMPTY`, `COMMENT_SUBMIT_MISSING`.

## F09 Repost the first post with thoughts

- Command: `python main.py repost --thoughts "..."`
- Input: thoughts text, or an AI generator.
- Success: the share dialog closes and the repost appears.
- Failure: repost menu missing, "with your thoughts" option missing, empty thoughts, share button missing.
- Codes: `REPOST_MENU_MISSING`, `REPOST_OPTION_MISSING`, `REPOST_NO_THOUGHTS`, `REPOST_SHARE_MISSING`.

## F10 Engage the feed stream

- Command: `python main.py engage --action both --max-actions 10`
- Input: an action type and a count.
- Success: each post is liked or commented and the run reports how many succeeded.
- Failure: feed did not load, no posts found, AI unavailable, some posts failed.
- Codes: `FEED_LOAD_FAILED`, `FEED_NO_POSTS`, `AI_UNAVAILABLE`, `ENGAGE_POST_FAILED`.

## F11 Pursue a profile

- Command: `python main.py pursue "Name" --max-posts 5`
- Input: a profile name and which actions to take.
- Success: the profile is found, followed when asked, and its posts are liked or commented.
- Failure: profile not found, follow button missing, no posts found.
- Codes: `PROFILE_NOT_FOUND`, `PROFILE_FOLLOW_MISSING`, `PROFILE_NO_POSTS`.

## F12 Generate a content calendar

- Command: `python main.py generate-calendar --niche "fitness" --total-posts 30`
- Input: a niche and a count.
- Success: a file is written with the requested number of posts.
- Failure: AI unavailable, AI returned empty content, output folder missing.
- Codes: `AI_UNAVAILABLE`, `AI_EMPTY_RESPONSE`, `CALENDAR_WRITE_FAILED`.

## F13 Mention a person in a post

- Command: `python main.py post --text "..."` with an anchor name in the text.
- Input: text containing a name to turn into a mention.
- Success: the mention is inserted as a real LinkedIn entity.
- Failure: typeahead did not open, no suggestion matched, mention could not be confirmed.
- Codes: `MENTION_TYPEAHEAD_MISSING`, `MENTION_NO_MATCH`, `MENTION_NOT_CONFIRMED`.

## F14 Verify that a post was published

- Command: internal, after F03, F04, F05 and F09.
- Input: the post modal or the feed after submitting.
- Success: a toast or the new post is seen within the timeout.
- Failure: modal closed with an error, timeout with no confirmation.
- Codes: `POST_VERIFY_TIMEOUT`, `POST_VERIFY_ERROR_SHOWN`.
