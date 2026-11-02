# Phase 3c brief: build_app, thin bot, no facade

## Goal

One function builds the graph. `LinkedInBot` becomes a thin orchestrator over
the services. The temporary facade `laf/services/interaction.py` is deleted.
`main.py` passes the settings in, and nothing changes a module global.

Files you may touch:

- `laf/app.py`, `main.py`, `laf/services/__init__.py`,
  `laf/browser/driver.py`, `laf/ai/client.py`
- `tests/test_main.py`, `tests/test_services.py`
- delete `laf/services/interaction.py`

Files you may NOT touch: other service files, `laf/config.py`,
`laf/errors.py`, `laf/messages.py`, `laf/ui.py`, anything under `laf/ai/`
other than `client.py`, `docs/`, `tests/` other than the two named.

## Contract

In `laf/app.py`:

```python
@dataclass
class Services:
    ui: UiActions
    overlays: OverlayService
    verify: VerifyService
    mentions: MentionService
    engage_dom: EngageDomService
    media: MediaService
    login: LoginService
    composer: ComposerService
    feed: FeedService
    profile: ProfileService
    engage: EngageService


@dataclass
class App:
    config: Config
    driver: WebDriver
    services: Services
    openai_client: Optional[OpenAIClient]
    content_generator: ContentGenerator
    post_extractor: PostExtractor


def build_app(
    config: Config | None = None,
    use_openai: bool = True,
    headless_override: bool | None = None,
    driver: WebDriver | None = None,
) -> App: ...
```

- `build_app` is the only place that builds a driver, the AI client, the
  content generator, the post extractor and the services.
- `config` defaults to `load_config(headless_override=headless_override)`.
  When `config` is given, `headless_override` is ignored, and say so in the
  `Args` block.
- `driver` is for tests: when given, it is used and the driver factory is not
  called. Still build every service around it.
- The AI client is built only when `use_openai` is true and
  `config.openai_api_key` is set, as today.
- `LinkedInBot.__init__(self, app: App)` stores the app and does not log in.
  Every flow that needs a session still calls `login` itself.
- `LinkedInBot` keeps the public methods `process_topics`, `post_custom_text`,
  `generate_content_calendar`, `pursue_investor` and `close`, with the same
  parameters. Internals call `self.app.services.<service>.<method>`.
- `close` quits `self.app.driver`, once.

`main.py`:

```python
bot = LinkedInBot(build_app(use_openai=not args.no_ai, headless_override=args.headless))
```

Delete the `config.HEADLESS = True` block and the `from laf import config`
import if it is no longer used. Keep the existing error handling.

`driver.py`: `DriverFactory.setup_driver(config: Config)` and the option
builders take that `Config` instead of reading module constants. Update the
call site and any other caller. Do not change the fallback order.

`ai/client.py`: remove the module level `client = OpenAI(...)`. Build the
client inside `OpenAIClient.__init__` from the injected `Config` (default
`CONFIG`), keep `self.client`, and keep the existing `AiError` behaviour.

Do not export `build_app` from `laf/services/__init__.py`: `laf.app` imports
the services package, so a services import of `laf.app` closes a cycle.
Delete the `interaction` import and export, and leave the package exporting
the service classes only. `laf/app.py` imports the services directly.

## Tests

- `tests/test_services.py`: drop every `LinkedInInteraction` test. Build with
  `build_app(config=CONFIG, use_openai=False, driver=FakeDriver())` and assert
  each service is present, the driver is the fake one, and the two like-state
  rules still hold through `app.services.engage`.
- `tests/test_main.py`: `main.py` now builds through `build_app`. Patch
  `main.build_app` to return a stand-in app and `main.LinkedInBot` to a fake
  that takes the app. Keep the three boundary tests and their assertions.
- Add one test that `build_app` with `use_openai=False` leaves
  `openai_client` as None, and that with a fake driver the same fake comes
  back out.

## Edge cases

- `headless_override=None` must leave the environment value alone.
- With no driver passed and no Chrome installed, `build_app` must raise the
  existing `DriverError` and not a raw Selenium trace.
- `generate_content_calendar` must keep working when `openai_client` is None;
  read the current app.py behaviour and keep it.
- `pursue_investor` reads `self.linkedin.driver.get(...)` today; use
  `self.app.driver.get(...)`.
- The four pyright errors currently in `laf/app.py` must be gone: the `bool`
  attribute reads around lines 260 to 262 and the `perspective` literal at
  line 674. Do not silence them with a cast that hides a real bug: fix the
  value that is wrong.
- Delete `laf/services/interaction.py` only after no module imports it; check
  with grep.

## Definition of done

Report the final `build_app` signature, the `LinkedInBot` method list, the
`main.py` diff summary, the driver and AI client changes, and every test you
changed. Then paste:

```
uv run ruff check laf/ main.py tests/
uv run pytest -q
uv run pyright laf/ main.py
uv run python main.py --help
grep -rn "LinkedInInteraction\|from .interaction" laf/ tests/ main.py
```

`pytest`, `pyright` on `laf/` and `main.py --help` must pass. `ruff` may
report only E501. Do not commit.
