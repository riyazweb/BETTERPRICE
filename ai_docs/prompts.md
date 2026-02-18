# Prompt History — PricePulse

> This document records the iterative prompts used to develop PricePulse through AI-assisted engineering. Each entry includes the original intent, the exact prompt used, what was produced, and what I had to course-correct. This is a real audit trail of the AI collaboration process — not a cleaned-up summary.

---

## Why This Document Exists

Building with AI assistance isn't magic. It requires careful prompt engineering, reviewing output critically, and pushing back when the AI oversimplifies or over-engineers. This file documents that process so the codebase decisions aren't mysterious — they're traceable.

---

## Prompt 1 — Architecture Foundation

**Goal:** Take a single-file Flask proof-of-concept and refactor it into a production-ready structure.

**Prompt sent:**
> "I have a Flask app that does price comparison using BeautifulSoup. It's all in one file — one route, one scraper function, no validation, no database. I want to refactor it into a layered architecture: Flask Application Factory, a service layer for scraping logic, Pydantic schemas for request/response validation, SQLAlchemy with a SearchHistory model for persistence, and pytest for testing. Show me the full directory structure and the starting files."

**What came out:**
- Flask Application Factory pattern in `app/__init__.py` with `create_app()`
- Blueprint registration for `/api/v1` routes
- Separate `config.py` with `DevelopmentConfig` and `TestingConfig`
- `BaseScraper` abstract class in `services.py`
- `SearchHistory` SQLAlchemy model in `models.py`
- Initial Pydantic schemas for `PriceRequest` and `ProductResponse`
- Basic `run.py` entry point

**What I had to correct:**
- The initial `create_app()` put database initialization outside the app context which caused `RuntimeError: No application found` — pushed back and the DB init was moved inside the `with app.app_context():` block.
- `ProductResponse` initially used `extra="ignore"` which would silently drop unexpected fields — changed to `extra="forbid"` to make the contract strict.

---

## Prompt 2 — Strict Validation Layer

**Goal:** Tighten up request and response validation so no invalid data can reach the service or leave the API.

**Prompt sent:**
> "Enforce strict validation at both the request and response layer. For the request: use Pydantic's `extra='forbid'` and add a URL field validator that extracts the domain and checks it against a list of supported marketplaces. If the domain isn't in the list, raise a 422 before any scraping happens. For the response: validate with `ProductResponse.model_validate()` before jsonifying — never return raw dict output from the service."

**What came out:**
- `detect_marketplace(url: str) -> str` helper function in `schemas.py` using `urllib.parse.urlparse`
- `@field_validator("url")` on `PriceRequest` that calls `detect_marketplace()` and raises `ValueError` for unsupported domains
- Supported marketplace list: `amazon.in`, `flipkart.com` — extensible by adding to a constant
- `routes.py` updated to call `ProductResponse.model_validate(result)` with a try/except that maps `ValidationError` to a 500

**What I had to correct:**
- The validator initially raised a plain `ValueError` with the full domain string embedded in the message, which leaked internal data in the API response. Changed the message to a generic "Unsupported marketplace" string.
- The `routes.py` error handler for `ValidationError` was using `str(e)` which included Pydantic's internal representation. Replaced with a sanitized error message.

---

## Prompt 3 — Scraper Abstraction and Change Resilience

**Goal:** Make sure the scraping logic is completely isolated from routes so a future provider swap is a one-file change.

**Prompt sent:**
> "Create an abstract `BaseScraper` with a single abstract method `scrape(url: str) -> ScrapeResult`. Use `@dataclass(frozen=True)` for `ScrapeResult` so it's an immutable value object. Implement `MarketplaceScraper(BaseScraper)` using requests + BeautifulSoup. Inject the scraper into `PriceComparisonService.__init__()` so it can be swapped in tests. The routes.py file must not import anything from beautifulsoup4 or requests — if it does, that's a hard violation."

**What came out:**
- `ScrapeResult` frozen dataclass with fields: `title`, `price`, `image_url`, `source`, `marketplace`, `status`, `error`
- `BaseScraper` ABC with abstract `scrape()` method
- `MarketplaceScraper` implementing BS4 parsing with timeout enforcement
- `PriceComparisonService.__init__` accepting optional `scraper: BaseScraper` parameter, defaulting to `MarketplaceScraper()`
- Clean `routes.py` — zero imports from HTTP or parsing libraries

**What I had to correct:**
- `ScrapeResult` initially had `status` as a bool — changed to a string enum (`"success"` / `"error"`) so the API contract is human-readable.
- The default scraper was instantiated at module import time rather than inside `__init__` — causes issues with test mocking. Fixed to instantiate per-service instance.

---

## Prompt 4 — Failure Handling and Error Mapping

**Goal:** Make failure cases explicit, each mapped to the right HTTP status code and logged with context.

**Prompt sent:**
> "Add explicit exception classes: `ScraperTimeoutError`, `ProductNotFoundError`, `BotDetectedError`. In `MarketplaceScraper.scrape()`, catch `requests.exceptions.Timeout`, HTTP 404, and HTTP 503 separately and raise the matching custom exception. In `routes.py`, catch each type explicitly and return the correct HTTP code: 408 for timeout, 404 for not found, 503 for bot detection. In `PriceComparisonService.compare()`, log and persist the failure in `SearchHistory` for every exception type — do not use a single broad except clause."

**What came out:**
- Three custom exception classes in `services.py`
- Explicit `except` blocks in `MarketplaceScraper.scrape()` for each HTTP error type
- `routes.py` with type-specific handlers returning correct status codes
- `SearchHistory` writes on both success and failure with `status` and `error` fields populated correctly

**What I had to correct:**
- The initial implementation had a final `except Exception` catch-all in `compare()` "just in case" — removed this because it could mask unhandled bugs. Each error type should be explicit or the error should propagate.
- `SearchHistory` was only being written on success — missed the failure paths. Added explicit DB writes in each `except` block.

---

## Prompt 5 — React Frontend with Production UX

**Goal:** Build a clean, professional frontend that handles loading states, error conditions, and edge cases without silently failing.

**Prompt sent:**
> "Build a React + Tailwind frontend using Vite. Design it around brand color `#01487e`. It should: POST to `/api/v1/compare` with the user's URL, show a loading state while waiting, display product image + title + price + marketplace in a clean card, show a bar chart comparing the found price against estimated alternatives, surface a dismissed toast on any API error, and show search history from GET `/api/v1/history`. The component must handle invalid JSON responses from the API without throwing — use `.catch(() => ({}))` on the `.json()` call."

**What came out:**
- Single-page `App.jsx` with URL input, submit handler, and result display
- `#01487e` as primary brand color throughout
- Loading spinner with status message
- `ProductCard` section with image, title, price
- Bar chart built with inline Tailwind bars (no extra chart library dependency)
- History section fetching from `/api/v1/history` on mount
- Safe `.json().catch(() => ({}))` on fetch error paths

**What I had to correct:**
- The initial chart used `recharts` as a dependency — removed in favor of pure Tailwind bars to keep the bundle lean and avoid an extra install step.
- Error toasts initially used `alert()` — replaced with a dismissible inline toast component.
- Clipboard copy for URL used `navigator.clipboard.writeText()` without a try/catch — some browsers block this in non-HTTPS contexts. Added a `.catch()` fallback to show a toast instead of crashing silently.

---

## Prompt 6 — Test Suite Completion

**Goal:** Cover the full happy path, validation rejections, and all upstream failure scenarios with pytest.

**Prompt sent:**
> "Write a comprehensive pytest test suite using `TestingConfig` in-memory SQLite. Cover: health check 200, valid compare success (mock `app.services.MarketplaceScraper.scrape`), invalid URL 422, unsupported marketplace 422, missing body field 422, timeout → 408, bot detection → 503, product not found → 404, history empty 200, history populated after compare 200. Assert both status codes and response JSON structure every time. Never make real HTTP calls — mock at `app.services.MarketplaceScraper.scrape`."

**What came out:**
- 11 tests covering all listed scenarios
- `@pytest.fixture` for test client using `TestingConfig`
- `unittest.mock.patch` at `app.services.MarketplaceScraper.scrape` for all mocked tests
- Assertions on both HTTP status and JSON body shape
- History population test verifies that a `/compare` call results in a new row in `/history`

**What I had to correct:**
- Two tests were initially asserting exact error message strings — brittle if messages change. Changed to asserting on `response.json["status"] == "error"` and the HTTP code only.
- The fixture was creating a new app per-test but not dropping the DB table between tests, so history tests were order-dependent. Added `db.drop_all()` + `db.create_all()` in the fixture teardown.
