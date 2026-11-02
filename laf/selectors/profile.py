"""Selectors for searching and interacting with user profiles.

WHY
  Serve the profile search box, results and posts tab, so a profile page change
  has one file to update.
"""


class ProfileSelectors:
    """Selectors for searching and interacting with user profiles.

    WHY
      Serve the profile search, result and posts tab lookups, so a profile page
      change has one file to update.
    """

    SEARCH_INPUT = "input[role='combobox']"  # linkedin_ui/profile_actions.py:33
    PEOPLE_TAB = (
        "//*[(self::button or self::a) and contains(normalize-space(), 'People') and "
        "(contains(@href, 'people') or contains(@class, 'filter-pill') or "
        "contains(@class, 'search-reusables'))]"
    )  # linkedin_ui/profile_actions.py:44
    SEARCH_RESULTS = (
        "//div[@role='list']//div[@role='listitem'][.//a[contains(@href, '/in/')]]"
    )  # linkedin_ui/profile_actions.py:56
    PROFILE_LINK = ".//a[contains(@href,'/in/')]"  # linkedin_ui/profile_actions.py:68
    FOLLOW_BUTTON = (
        "//button[.//*[contains(text(),'Follow')]]"  # linkedin_ui/profile_actions.py:112
    )
    POSTS_TAB_BUTTON = (
        "//button[.//span[normalize-space()='Posts']]"  # linkedin_ui/profile_actions.py:144
    )

    SHOW_ALL_POSTS = [
        (
            "//a[contains(@class,'profile-creator-shared-content-view__footer-action') "
            "and .//span[normalize-space()='Show all posts']]"
        ),
        (
            "//a[contains(@href,'recent-activity/all') and "
            ".//span[normalize-space()='Show all posts']]"
        ),
    ]  # linkedin_ui/profile_actions.py:129

    POST_LINKS = (
        "a.app-aware-link[href*='/posts/'], "
        "a.app-aware-link[href*='/recent-activity/']"
    )  # linkedin_ui/profile_actions.py:181

    POST_CONTAINER = "div.feed-shared-update-v2"  # linkedin_ui/profile_actions.py:340
    ACTION_BAR_CSS = "div.social-details-social-actions"  # linkedin_ui/profile_actions.py:346
