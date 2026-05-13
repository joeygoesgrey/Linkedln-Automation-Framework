from selenium.webdriver.common.by import By

"""Central registry for LinkedIn UI selectors.

Why:
    Hardcoded selectors in logic files are hard to track and maintain.
    Centralizing them here makes it easy to update selectors when LinkedIn's UI changes.

When:
    Import these classes whenever a `By.XPATH` or `By.CSS_SELECTOR` string is needed
    for locating elements in the LinkedIn DOM.
"""

class LoginSelectors:
    """Selectors used during the login and 2FA process."""

    SIGN_IN_LINK = "a[href*='signin']"  # linkedin_ui/login.py:68
    USERNAME_FIELDS = [
        "input#username",
        "input[name='session_key']",
        "input[autocomplete*='username']",
        "input[type='email']",
        (By.XPATH, "//input[@type='email' or contains(@autocomplete, 'username')]")
    ]  # linkedin_ui/login.py:81
    PASSWORD_FIELDS = [
        "input#password",
        "input[name='session_password']",
        "input[autocomplete*='current-password']",
        "input[type='password']",
        (By.XPATH, "//input[@type='password' or contains(@autocomplete, 'password')]")
    ]  # linkedin_ui/login.py:100
    SUBMIT_BUTTONS = [
        "button[type='submit']",
        "button.sign-in-form__submit-button",
        "button[data-litms-control-urn='login-submit']",
        (By.XPATH, "//button[.//span[normalize-space()='Sign in']]")
    ]  # linkedin_ui/login.py:113
    VERIFICATION_PIN = "input#input__phone_verification_pin"  # linkedin_ui/login.py:128
    
    SUCCESS_INDICATORS = [
        (By.CSS_SELECTOR, "div.feed-identity-module"),
        (By.CSS_SELECTOR, "button[data-control-name='create_post']"),
        (By.XPATH, "//button[contains(.,'Start a post')]"),
        (By.CSS_SELECTOR, "div.share-box-feed-entry__avatar"),
    ]  # linkedin_ui/login.py:135


class VerifySelectors:
    """Selectors for verifying post submission success."""
    
    SUCCESS_INDICATORS = [
        "//div[contains(@class, 'artdeco-toast') and (contains(translate(., 'POSTEDSHARED', 'postedshared'), 'posted') or contains(translate(., 'POSTEDSHARED', 'postedshared'), 'shared'))]",
        "//div[contains(@class, 'artdeco-toast-item')]",
        "//div[contains(@class, 'toast') and contains(@role, 'alert')]",
        "//div[contains(@class, 'feed-shared-update-v2')]",
    ]  # linkedin_ui/verify.py:57
    
    POST_MODAL = "//div[@role='dialog' and contains(@class, 'share-box-modal')]"  # linkedin_ui/verify.py:74
    POST_MODAL_ERROR = ".//*[contains(@class, 'error') or contains(@class, 'alert')]"  # linkedin_ui/verify.py:79
    CLOSED_SHARE_BOX = "//div[contains(@class, 'share-box-feed-entry__closed-share-box')]"  # linkedin_ui/verify.py:91
    FEED_SNIPPET_TEMPLATE = "//div[contains(@class,'feed') or contains(@class,'scaffold')]//*[contains(normalize-space(.), \"{snippet}\")]"  # linkedin_ui/verify.py:98


class OverlaySelectors:
    """Selectors for finding and dismissing UI overlays."""
    
    CHAT_CLOSE_BUTTON = "//button[contains(@class, 'msg-overlay-bubble-header__control--close')]"  # linkedin_ui/overlays.py:64
    TOAST_CLOSE_BUTTON = "//button[contains(@class, 'artdeco-toast-item__dismiss')]"  # linkedin_ui/overlays.py:75
    SAVE_DRAFT_DIALOG = "//div[contains(@class, 'save-draft-dialog')]"  # linkedin_ui/overlays.py:86
    UNSAVED_DETOUR_DIALOG = "//div[contains(@class, 'unsaved-detour-dialog')]"  # linkedin_ui/overlays.py:100
    DIALOG_SECONDARY_BUTTON = ".//button[contains(@class, 'artdeco-button--secondary')]"  # linkedin_ui/overlays.py:89, 103
    MODAL_DISMISS_BUTTON = "//button[contains(@class, 'artdeco-modal__dismiss')]"  # linkedin_ui/overlays.py:115
    SHARE_MODAL_ANCESTOR = "ancestor::div[contains(@class,'share-box-modal')]"  # linkedin_ui/overlays.py:119
    
    COMPOSER_ROOTS = [
        "//div[@role='dialog' and contains(@class, 'share-creation-state')]",
        "//div[@role='dialog' and contains(@class, 'share-box-modal')]",
        "//div[contains(@class, 'share-box-modal')]",
    ]  # linkedin_ui/overlays.py:134
    
    DRAFT_MODAL = "//div[contains(@class,'artdeco-modal') and (.//button[normalize-space(.)='Save as draft'] or .//button[normalize-space(.)='Discard'])]"  # linkedin_ui/overlays.py:148
    DRAFT_MODAL_CLOSE_BUTTON = ".//button[contains(@class,'artdeco-modal__dismiss') or @aria-label='Dismiss' or @aria-label='Close']"  # linkedin_ui/overlays.py:153
    UNEXPECTED_CLOSE_BUTTON = "//button[@aria-label='Close' or @aria-label='Dismiss' or contains(@class, 'close-btn')]"  # linkedin_ui/overlays.py:172


class ComposerSelectors:
    """Selectors for the post composer and feed start buttons."""
    
    START_POST_TRIGGERS = [
        "//div[contains(@class, 'share-box-feed-entry__top-bar')]",
        "//div[contains(@class, 'share-box-feed-entry__closed-share-box')]",
        "//div[text()='Start a post']",
        "//button[contains(@class, 'share-box-feed-entry__trigger')]",
        "//button[contains(@aria-label, 'Start a post')]",
        "//div[contains(@class, 'share-box-feed-entry__trigger')]",
        "//button[contains(text(), 'Start a post')]",
        "//span[text()='Start a post']/ancestor::button",
        "//div[contains(@class, 'share-box')]",
    ]  # linkedin_ui/composer.py:331

    POST_EDITOR = [
        "//div[contains(@class, 'share-creation-state__editor-container')]//div[@role='textbox']",
        "//div[contains(@class, 'ql-editor')][contains(@data-gramm, 'false')]",
        "//div[contains(@class, 'ql-editor')]",
        "//div[contains(@role, 'textbox')]",
        "//div[@data-placeholder='What do you want to talk about?']",
        "//div[contains(@aria-placeholder, 'What do you want to talk about?')]"
    ]  # linkedin_ui/composer.py:372

    POST_BUTTON = [
        "//button[normalize-space(.)='Post']",
        "//span[normalize-space(.)='Post']/parent::button",
        "//button[normalize-space(.)='Schedule']",
        "//span[normalize-space(.)='Schedule']/parent::button",
        "//button[contains(@aria-label, 'Post')]",
        "//button[contains(@aria-label, 'Schedule')]",
        "//button[normalize-space(.)='Share']",
        "//span[normalize-space(.)='Share']/parent::button",
        "//button[contains(@aria-label, 'Share')]",
        "//button[normalize-space(.)='Publish']",
        "//span[normalize-space(.)='Publish']/parent::button",
        "//button[contains(@class, 'share-actions__primary-action')]",
        "//footer//button[contains(@class, 'artdeco-button') and not(@disabled)]",
    ]  # linkedin_ui/composer.py:424
    
    MODAL_ROOTS = [
        "//div[@role='dialog' and contains(@class, 'share-creation-state')]",
        "//div[@role='dialog' and contains(@class, 'share-box-modal')]",
        "//div[contains(@class, 'share-box-modal')]",
    ]  # linkedin_ui/composer.py:410

    SCHEDULE_BUTTONS = [
        "//button[contains(@class,'share-actions__scheduled-post-btn')]",
        "//button[@aria-label='Schedule post']",
        "//button[.//svg/*[contains(@data-test-icon,'clock')]]",
    ]  # linkedin_ui/composer.py:181

    SCHEDULE_DATE_INPUTS = [
        "//input[@id='share-post__scheduled-date']",
        "//input[@name='artdeco-date']",
        "//input[@aria-label='Date']",
        "//div[contains(@class,'artdeco-datepicker__input')]//input",
    ]  # linkedin_ui/composer.py:204

    SCHEDULE_TIME_INPUTS = [
        "//input[@id='share-post__scheduled-time']",
        "//input[@aria-label='Time']",
        "//div[contains(@class,'timepicker')]//input",
    ]  # linkedin_ui/composer.py:230

    SCHEDULE_NEXT_BUTTONS = [
        "//button[contains(@class, 'share-box-footer__primary-btn') and contains(., 'Next')]",
        "//div[contains(@class, 'share-box-footer__main-actions')]//button[@aria-label='Next']",
        "//button[.//span[normalize-space()='Next']]",
        "//button[@aria-label='Next']",
        "//div[contains(@class,'share-box-footer')]//button[contains(.,'Next')]",
    ]  # linkedin_ui/composer.py:255

    SCHEDULE_CONFIRM_BUTTONS = [
        "//button[.//span[normalize-space()='Schedule']]",
        "//button[contains(@aria-label,'Schedule')]",
        "//button[contains(.,'Schedule')]",
    ]  # linkedin_ui/composer.py:297


class MediaSelectors:
    """Selectors for uploading media and interacting with the media tray."""
    
    PHOTO_BUTTONS = [
        "button.share-box-feed-entry-toolbar__item[aria-label='Add a photo']",
        "button.image-detour-btn",
        "button[aria-label='Add a photo']",
        "//button[contains(@aria-label, 'photo')]",
        "//button[contains(@title, 'Add a photo')]",
        "//button[contains(@aria-label, 'Add to your post')]",
    ]  # linkedin_ui/media.py:148
    
    MODAL_PHOTO_BUTTONS = [
        "button[aria-label*='Add media']",
        "//button[contains(@aria-label, 'Add media')]",
        "//button[contains(normalize-space(.), 'Add media')]",
        "button.share-promoted-detour-button[aria-label='Add media']",
        "//button[.//span[contains(@class, 'share-promoted-detour-button__icon-container')]//*[contains(@data-test-icon, 'image-medium')]]",
        "//li[contains(@class, 'artdeco-carousel__item')]//button[.//svg[contains(@data-test-icon, 'image')]]",
        ".share-creation-state__promoted-detour-button-item button",
        "//button[.//svg[contains(@data-test-icon, 'image')]]",
        "//button[.//*[local-name()='svg' and contains(@data-test-icon,'image')]]",
    ]  # linkedin_ui/media.py:156
    
    COMPOSER_ROOTS = ComposerSelectors.MODAL_ROOTS
    
    MODAL_ROOTS = [
        "//div[@role='dialog' and contains(@class,'share-box-v2__modal')]",
        "//div[@role='dialog' and contains(@class,'share-box-modal')]",
        "//div[contains(@class,'media-editor__container')]/ancestor::div[@role='dialog']",
    ]  # linkedin_ui/media.py:222

    FILE_INPUTS = [
        "#media-editor-file-selector__file-input",
        "input.media-editor-file-selector__upload-media-input",
        "input#media-editor-file-selector__file-input",
        "input[id='media-editor-file-selector__file-input']",
        "//input[@id='media-editor-file-selector__file-input']",
        "//input[contains(@class, 'media-editor-file-selector__upload-media-input')]",
        "//div[contains(@class,'share') or contains(@class,'media') or contains(@class,'editor')]//input[@type='file']",
        "input[type='file']",
        "//input[@type='file']",
        "//div[contains(@class, 'share-box')]//input[@type='file']",
        "//div[contains(@class, 'share-creation-state')]//input[@type='file']",
        "//div[contains(@class, 'image-selector')]//input[@type='file']",
    ]  # linkedin_ui/media.py:236
    
    UPLOAD_LABEL = "//label[contains(normalize-space(.), 'Upload from computer')]"  # linkedin_ui/media.py:288
    
    PREVIEWS = [
        "//div[contains(@class,'image') or contains(@class,'media') or contains(@class,'preview')]//img",
        "//div[contains(@class,'media-editor')]//img",
        "//img[contains(@src,'data:') or contains(@src,'media')]",
    ]  # linkedin_ui/media.py:94
    
    IFRAME_INPUTS = ["input[type='file']", "//input[@type='file']"]  # linkedin_ui/media.py:395
    
    POST_UPLOAD_BUTTONS = [
        "button.share-box-footer__primary-btn:not([disabled])",
        "button.artdeco-button--primary:not([disabled])",
        "button[aria-label='Next']",
        "button[aria-label='Done']",
        "button[aria-label='Add']",
        "button.media-editor-toolbar__submit-button",
        "//button[contains(text(),'Next')]",
        "//button[contains(text(),'Done')]",
        "//button[contains(text(),'Add')]",
        "//button[contains(@class, 'share-creation-state__submit')]",
        "//div[contains(@class, 'share-box-footer')]//button[contains(@class, 'artdeco-button--primary')]",
    ]  # linkedin_ui/media.py:461
    
    BACK_BUTTON = "//button[contains(text(),'Back')]"  # linkedin_ui/media.py:489


class MentionSelectors:
    """Selectors for mentioning users/entities in the composer."""
    
    SUGGESTIONS = [
        "//div[contains(@class,'typeahead') and contains(@class,'artdeco')]//li",
        "//div[contains(@class,'mentions') and contains(@class,'suggest')]//li",
        "//div[contains(@class,'ember-view') and contains(@class,'typeahead')]//li",
        "//div[contains(@class,'editor-typeahead-fetch')]//*[self::li or self::button or self::a]",
        "//div[contains(@role,'listbox')]//li",
        "//ul[contains(@class,'suggest') or contains(@class,'results')]//li",
    ]  # linkedin_ui/mentions.py:341

    TYPEAHEAD_CONTAINERS = [
        "//div[contains(@class,'editor-typeahead-fetch')]",
        "//div[contains(@class,'typeahead') and contains(@class,'artdeco')]",
        "//div[contains(@class,'mentions') and contains(@class,'suggest')]",
        "//div[contains(@role,'listbox')]",
    ]  # linkedin_ui/mentions.py:398

    ENTITY_TEMPLATES = [
        ".//*[contains(@class,'ql-mention') and contains(normalize-space(.), \"{t}\")]",
        ".//*[contains(@class,'mention') and contains(normalize-space(.), \"{t}\")]",
        ".//*[contains(@class,'entity') and contains(normalize-space(.), \"{t}\")]",
        ".//a[contains(normalize-space(.), \"{t}\")]",
    ]  # linkedin_ui/mentions.py:497

    FIRST_SUGGESTION_ROOTS = [
        "//div[contains(@class,'editor-typeahead-fetch')]",
        "//div[contains(@class,'typeahead') and contains(@class,'artdeco')]",
    ]  # linkedin_ui/mentions.py:563

    FIRST_SUGGESTION_OPTIONS = [
        ".//div[contains(@class,'basic-typeahead__selectable') and @role='option'][1]",
        ".//*[@role='option'][1]",
        ".//li[1]",
    ]  # linkedin_ui/mentions.py:575

    FALLBACK_SUGGESTIONS = [
        "//div[contains(@class,'typeahead') and contains(@class,'artdeco')]//li[.//button or .]",
        "//div[contains(@class,'mentions') and contains(@class,'suggest')]//li",
        "//div[contains(@role,'listbox')]//li",
        "//ul[contains(@class,'suggest') or contains(@class,'results')]//li",
    ]  # linkedin_ui/mentions.py:602


class PostExtractorSelectors:
    """Selectors for extracting text and metadata from feed posts."""

    SEE_MORE_BUTTONS = [
        ".//button[contains(@class,'see-more') and contains(@class,'inline-show-more-text__button')]",
        ".//span[contains(@class,'line-clamp-show-more-button')]",
        ".//button[normalize-space()='...see more']",
        ".//button[normalize-space()='Show more']",
    ]  # linkedin_ui/post_extractor.py:98

    CONTENT_NODES = (
        ".//div[contains(@class,'update-components-text')]//*[normalize-space()]",
        ".//div[contains(@class,'feed-shared-inline-show-more-text')]//*[normalize-space()]",
        ".//div[contains(@class,'feed-shared-article__description')]//*[normalize-space()]",
        ".//span[contains(@class,'break-words') and normalize-space()]",
    )  # linkedin_ui/post_extractor.py:140


class EngageSelectors:
    """Selectors for DOM traversal and interaction during the engage stream."""
    
    AUTHOR_NAME = [
        ".//span[contains(@class,'update-components-actor__title')]//span[normalize-space() and not(contains(@class,'visually-hidden'))]",
        ".//div[contains(@class,'update-components-actor__container')]//a[contains(@href,'/in/')][normalize-space()]",
        ".//a[contains(@class,'update-components-actor__meta-link')]//*[normalize-space() and not(contains(@class,'visually-hidden'))]",
    ]  # linkedin_ui/engage_dom.py:62
    
    VISIBLE_POSTS = [
        "//div[@data-id]",
        "//div[contains(@class,'fie-impression-container')]",
        "//div[contains(@class,'feed-shared-update-v2__control-menu-container')]/div[contains(@class,'fie-impression-container')]",
        "//div[contains(@class,'feed-shared-update-v2')]",
    ]  # linkedin_ui/engage_dom.py:149
    
    POST_ROOT_FROM_BAR = [
        ".//ancestor::div[contains(@class,'feed-shared-update-v2')][1]",
        ".//ancestor::div[contains(@data-urn,'activity')][1]",
        ".//ancestor::article[1]",
    ]  # linkedin_ui/engage_dom.py:348
    
    TEXT_SNIPPETS = ".//div[contains(@class,'update-components-text') or contains(@class,'feed-shared-inline-show-more-text')]//*[normalize-space()]"  # linkedin_ui/engage_dom.py:487, 734
    
    USER_COMMENT_MARKERS = [
        ".//*[contains(@class,'comments-comment-item')]//*[contains(normalize-space(.),'You')]",
        ".//*[contains(@class,'comments-comment-item')]//*[contains(normalize-space(.),'you')]",
    ]  # linkedin_ui/engage_dom.py:520
    
    ALL_COMMENTS = [
        ".//*[contains(@class,'comments-comment-item')]//*[normalize-space()]",
    ]  # linkedin_ui/engage_dom.py:567
    
    AI_TEXT_NODES = [
        ".//div[contains(@class,'update-components-text')]//*[normalize-space()]",
        ".//div[contains(@class,'feed-shared-update-v2__description')]//*[normalize-space()]",
        ".//span[contains(@class,'break-words') and normalize-space()]",
    ]  # linkedin_ui/engage_dom.py:616
    
    PROMOTED_MARKER = ".//*[contains(translate(normalize-space(.),'PROMOTED','promoted'),'promoted')]"  # linkedin_ui/engage_dom.py:770
    
    ACTION_BAR = ".//div[contains(@class,'feed-shared-social-action-bar')]"  # linkedin_ui/engage_flow.py:356
    
    LIKE_BUTTONS = [
        ".//button[contains(@class,'react-button__trigger')]",
        ".//button[@aria-label='React Like']",
        ".//button[.//span[normalize-space()='Like']]",
    ]  # linkedin_ui/engage_dom.py:805
    
    COMMENT_BUTTONS = [
        ".//button[contains(@class,'comment-button')]",
        ".//button[@aria-label='Comment']",
        ".//button[.//span[normalize-space()='Comment']]",
    ]  # linkedin_ui/engage_dom.py:858
    
    COMMENT_EDITOR = [
        ".//div[@contenteditable='true' and contains(@class,'comments')]",
        ".//div[@contenteditable='true' and contains(@role,'textbox')]",
        ".//form[contains(@class,'comments')]//div[@contenteditable='true']",
    ]  # linkedin_ui/engage_dom.py:881
    
    SUBMIT_COMMENT = [
        "//button[contains(@class,'comments-comment-box__submit-button')]",
        "//button[.//span[normalize-space()='Post']]",
        "//button[@data-control-name='submit_comment']",
    ]  # linkedin_ui/engage_dom.py:988


class FeedActionSelectors:
    """Selectors for feed actions (like, comment, repost)."""
    
    FIRST_ACTION_BAR = [
        "(//div[contains(@class,'feed-shared-social-action-bar')])[1]",
        "(//div[contains(@class,'update-v2-social-activity')]//div[contains(@class,'social-action')])[1]",
    ]  # linkedin_ui/feed_actions.py:80
    
    LIKE_BUTTONS = EngageSelectors.LIKE_BUTTONS
    
    COMMENT_BUTTONS = EngageSelectors.COMMENT_BUTTONS
    
    COMMENT_EDITOR = [
        "(//div[@contenteditable='true' and (contains(@class,'comments') or contains(@class,'ql-editor') or contains(@role,'textbox'))])[1]",
        "(//div[contains(@class,'comments') and @contenteditable='true'])[1]",
    ]  # linkedin_ui/feed_actions.py:204
    
    SUBMIT_COMMENT = EngageSelectors.SUBMIT_COMMENT
    
    REPOST_BUTTONS = [
        ".//button[contains(@class,'social-reshare-button')]",
        ".//button[.//span[normalize-space()='Repost']]",
        ".//button[@data-finite-scroll-hotkey='r']",
    ]  # linkedin_ui/feed_actions.py:326
    
    REPOST_DROPDOWN_CONTAINERS_SCOPED = [
        ".//div[contains(@class,'artdeco-dropdown__content')]",
        ".//div[contains(@class,'social-reshare-button__share-dropdown-content')]",
        "//div[contains(@class,'artdeco-dropdown__content')]",
    ]  # linkedin_ui/feed_actions.py:349
    
    REPOST_DROPDOWN_CONTAINERS_GLOBAL = "//div[contains(@class,'artdeco-dropdown__content')]"  # linkedin_ui/feed_actions.py:364
    
    REPOST_OPTION_TAGS = [
        ".//button",
        ".//*[@role='menuitem']",
        ".//li",
        ".//div",
        ".//span",
    ]
    
    REPOST_CANDIDATE_TEXTS = [
        "repost with your thoughts",
        "repost with thoughts",
        "share with your thoughts",
        "reshare with your thoughts",
    ]
    
    REPOST_GLOBAL_OPTION_XPATH_TEMPLATE = "//*[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), '{cand}')]"

    
    REPOST_EDITOR = [
        "//div[contains(@class,'editor-container')]//div[@contenteditable='true']",
        "//div[contains(@class,'ql-editor') and @contenteditable='true']",
        "//div[@contenteditable='true' and contains(@aria-label,'Text editor')]",
    ]  # linkedin_ui/feed_actions.py:457
    
    SUBMIT_REPOST = [
        "//button[.//span[normalize-space()='Post']]",
        "//button[contains(@aria-label,'Post')]",
        "//button[.//span[normalize-space()='Share']]",
        "//button[contains(@aria-label,'Share')]",
    ]  # linkedin_ui/feed_actions.py:538


class ProfileSelectors:
    """Selectors for searching and interacting with user profiles."""
    
    SEARCH_INPUT = "input[role='combobox']"  # linkedin_ui/profile_actions.py:33
    PEOPLE_TAB = "//*[(self::button or self::a) and contains(normalize-space(), 'People') and (contains(@href, 'people') or contains(@class, 'filter-pill') or contains(@class, 'search-reusables'))]"  # linkedin_ui/profile_actions.py:44
    SEARCH_RESULTS = "//*[contains(concat( ' ', @class, ' ' ), concat( ' ', '_455d2a19', ' ' ))] | //main//li[.//a[contains(@href, '/in/') and not(contains(@href, 'linkedin.com/in/'))]] | //li[contains(@class, 'reusable-search__result-container')]"  # linkedin_ui/profile_actions.py:56
    PROFILE_LINK = ".//a[contains(@href,'/in/')]"  # linkedin_ui/profile_actions.py:68
    FOLLOW_BUTTON = "//button[.//*[contains(text(),'Follow')]]"  # linkedin_ui/profile_actions.py:112
    POSTS_TAB_BUTTON = "//button[.//span[normalize-space()='Posts']]"  # linkedin_ui/profile_actions.py:144
    
    SHOW_ALL_POSTS = [
        "//a[contains(@class,'profile-creator-shared-content-view__footer-action') and .//span[normalize-space()='Show all posts']]",
        "//a[contains(@href,'recent-activity/all') and .//span[normalize-space()='Show all posts']]",
    ]  # linkedin_ui/profile_actions.py:129
    
    POST_LINKS = "a.app-aware-link[href*='/posts/'], a.app-aware-link[href*='/recent-activity/']"  # linkedin_ui/profile_actions.py:181
    
    POST_CONTAINER = "div.feed-shared-update-v2"  # linkedin_ui/profile_actions.py:340
    ACTION_BAR_CSS = "div.social-details-social-actions"  # linkedin_ui/profile_actions.py:346
