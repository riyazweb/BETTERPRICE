# Coding Standards — PricePulse

> These standards were written during the development process to document the engineering decisions that shaped this codebase. They exist so that any future contributor — human or AI — understands not just *what* the rules are, but *why* they exist in the first place.

---

## Why These Standards Exist

When I started building PricePulse, my first instinct was to dump everything into a single Flask file and iterate fast. That works for demos, but the moment you need to swap a scraper, add a new marketplace, or debug a silent failure at 2am, a tangled monolith becomes a liability.

The standards here came out of real decisions made during this build — moments where I had to choose between "quick and dirty" and "structured and maintainable." Every rule below was informed by at least one concrete tradeoff I actually faced.

---

## 1. Layer Boundaries Are Sacred

The codebase is split into four layers with a strict one-way dependency rule:

```
routes.py  →  services.py  →  models.py
                   ↓
             schemas.py (shared contract)
```

**Routes** only speak HTTP. They accept a request, call a service method, and return a response. They have no idea what BeautifulSoup is and never import it. This is intentional — if the route handler knows about scraping, you've already lost.

**Services** own all business logic. The `PriceComparisonService.compare()` method is the single entry point for a price lookup. It validates, fetches, persists, and logs. It returns a typed `ScrapeResult`, not a raw dictionary.

**Models** handle persistence and nothing else. They don't know what a URL is from a business perspective — they just store and retrieve rows.

**Schemas** are the shared language. `PriceRequest` and `ProductResponse` define what flows in and what flows out. Nothing bypasses them.

The rule is simple: **dependencies only go downward, never sideways, never skipped.**

---

## 2. Validation Happens at the Edge — Nowhere Else

Every incoming request hits a Pydantic schema with `extra="forbid"` before anything else runs. This is not optional. If you add a new field to `PriceRequest` but forget to add it to the schema, the request will be rejected — and that's the right behavior.

The URL validation specifically runs `detect_marketplace()` before any HTTP call is made. The reason: we should never make a network request to an unknown domain. It wastes time, exposes the server, and makes debugging a nightmare. Fail fast at the boundary.

On the way out, every response goes through `ProductResponse.model_validate()`. This gives us a hard guarantee that the shape of the response never drifts from the contract, even if someone changes the internals of `compare()`.

---

## 3. The Scraper Is Designed to Be Replaced

The entire scraping layer is built around `BaseScraper`, an abstract class with a single required method: `scrape(url: str) -> ScrapeResult`. The current implementation is `MarketplaceScraper`, which uses `requests` + `BeautifulSoup`. 

Here's the critical design point: **routes.py has never heard of `MarketplaceScraper`**. It calls `PriceComparisonService.compare()`, which internally uses whatever scraper is injected. Swapping to a paid API like SerpAPI or ScraperAPI means writing one new class and changing one line in the service — not touching routes, not touching tests, not touching schemas.

This pattern came from a real concern: scraping is brittle. Sites change layouts, add bot detection, rotate CAPTCHAs. If the scraper is tightly coupled to routes, every upstream change becomes a refactor. With the abstraction in place, it stays a configuration decision.

---

## 4. Every Search Gets Persisted — Including Failures

This was a deliberate choice that felt like overkill at first. Why log failed searches? 

Two reasons:
1. **Debugging**: If a URL consistently fails with a 503, that pattern shows up in `SearchHistory`. Without it, you're blind to systemic issues.
2. **Honesty**: The search happened. The user asked for it. Pretending it didn't exist because it failed is misleading data.

`SearchHistory` is written on both the success path and the failure path inside `PriceComparisonService.compare()`. The `status` field and `error` field capture what happened. This is enforced in tests — if either path doesn't write to the DB, a test will fail.

---

## 5. Error Handling Is Explicit, Never Generic

```python
# This is never acceptable:
try:
    result = scraper.scrape(url)
except Exception as e:
    return {"error": str(e)}

# This is the standard:
except requests.exceptions.Timeout:
    raise ScraperTimeoutError(url)
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 404:
        raise ProductNotFoundError(url)
    if e.response.status_code == 503:
        raise BotDetectedError(url)
```

Broad `except Exception` catches hide bugs. They also make it impossible to return meaningful HTTP status codes to the client. Each error type maps to a specific HTTP response in `routes.py`, and each is logged with its own context. New error conditions get new exception classes — they don't get folded into a generic catch.

---

## 6. Observability Is Part of the Feature

Logs use `app.logger` with a structured `context` dict, not bare `print()` statements. The `context` dict always includes the URL and marketplace so any single log line is queryable without digging through surrounding lines.

Three log events are emitted per search:
- `"Search started"` — immediately before any scraping begins
- `"Search succeeded"` — after a successful scrape and DB write
- `"Search failed"` — after any exception is caught and mapped

This gives a complete audit trail. If a search shows "started" but no "succeeded" or "failed", there's an unhandled code path — and that's immediately actionable.

---

## 7. Tests Are the Contract, Not Documentation

Documentation drifts. Tests either pass or they don't.

Every route has a corresponding test. Every error path has a test. The test suite uses `TestingConfig` with an in-memory SQLite database — it never touches the development database and never makes real HTTP calls. `MarketplaceScraper.scrape` is always mocked at `app.services.MarketplaceScraper.scrape`.

Adding a new endpoint without a test is not acceptable. Not because of a rule, but because without the test, you have no way to know if the route contract remains stable as the internals evolve.

---

## 8. Style Decisions That Aren't Up for Debate

- **Type annotations on all function signatures** — not for static analysis tools, but for readability. A function signature is documentation.
- **`@dataclass(frozen=True)` for value objects** — `ScrapeResult` is immutable by design. Mutable return types cause subtle bugs when the same object is modified in multiple places.
- **Functions stay under 40 lines** — if a function is longer, it's doing too many things. Extract a helper.
- **No abbreviations** — `marketplace` is always `marketplace`, never `mktpl` or `mp`. The three characters you save aren't worth the confusion six months later.

---

## Known Limitations and Future Work

| Area | Current State | What Would Improve It |
|------|--------------|----------------------|
| Scraping reliability | BeautifulSoup on live HTML — fragile | Integrate a paid scraping API with structured output |
| Marketplace coverage | Amazon + Flipkart only | Add adapter classes per marketplace in `services.py` |
| Rate limiting | None in place | Add per-IP rate limit via Flask-Limiter |
| Async support | Fully synchronous | Migrate `PriceComparisonService` to async with `aiohttp` |
| Auth | No user accounts | JWT-based auth layer without touching core service logic |

None of these require modifying the existing architecture. They're extensions, not rewrites — which is the point.
