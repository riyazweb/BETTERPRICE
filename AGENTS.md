# AGENTS.md — AI Agent Constraints for PricePulse

> This file tells any AI agent — Copilot, Claude, Cursor, or anything else — exactly what it is and isn't allowed to do in this codebase. If you're an AI reading this: follow these rules completely. If you're a human reviewing AI output: this is the checklist you use to accept or reject it.

---

## Why This File Exists

AI assistants are powerful but they have a tendency to "help" in ways that weren't asked for — refactoring code that didn't need it, adding abstractions for hypothetical future cases, or quietly changing an interface that other code depends on. This file prevents that.

Every rule here was written to protect something specific: a contract, a separation of concerns, a test assumption, or a security boundary. The rules aren't arbitrary. If something seems overly restrictive, there's a reason for it explained in `ai_docs/coding_standards.md`.

---

## 1. What Each Layer Is Allowed to Touch

| File | You MAY do this | You MUST NOT do this |
|------|----------------|----------------------|
| `routes.py` | Add or modify endpoints; add new error type handlers | Import or call any HTTP client; embed scraping logic; embed business rules |
| `services.py` | Add a new `BaseScraper` subclass; extend `PriceComparisonService` with new methods | Change the signature of `compare()`; put route logic here |
| `schemas.py` | Add new fields with validators; tighten existing validators | Remove any validator; change `extra="forbid"` to anything else |
| `models.py` | Add new columns; add indexes; add new model classes | Drop or rename columns without a migration; alter table structure destructively |
| `tests/` | Add new tests for new behavior; add fixtures | Delete any existing test; weaken an assertion (e.g., changing `==` to `in`) |
| `frontend/src/` | Add new UI sections; add new API calls; extend the history view | Remove the loading state; remove the error toast; remove the `.catch()` on `.json()` |

If a request requires changes outside these boundaries, stop and explain why rather than proceeding anyway.

---

## 2. Hard Rules — These Are Never Negotiable

### Input and Output Validation

Every request body must be validated against a Pydantic schema that has `extra="forbid"`. This means if a client sends an unexpected field, the request is rejected with a 422 — not silently ignored, not passed through. The reason: unknown fields in a request are a signal of either a bug or a probing attack. Reject them explicitly.

Every API response must go through `ProductResponse.model_validate()` before being passed to `jsonify()`. The service layer returns a `ScrapeResult` dataclass, not a dict. The route layer's job is to validate that result into the public response shape. If validation fails here, it means the service returned something the contract doesn't expect — that's a 500, logged and surfaced explicitly.

URL domain validation via `detect_marketplace()` must happen inside the Pydantic schema validator, before any service method is called. We never make a network request to an unknown domain.

### Separation of Concerns

Route handlers must never import from `beautifulsoup4`, `requests`, `httpx`, or any HTTP library directly. If you see an import like `from bs4 import BeautifulSoup` inside `routes.py`, that is a violation.

All scraping logic — HTML parsing, HTTP headers, retry logic, response validation — lives in a `BaseScraper` subclass in `services.py`. The route handler calls `service.compare(url)` and gets back a typed result. It does not know or care how that result was obtained.

Adding support for a new marketplace must only require writing a new class in `services.py`. If it also requires changing `routes.py`, the abstraction has been broken.

### Data Integrity

`SearchHistory` must be written on every `/compare` call. This includes both the success path and every failure path. If you add a new exception type to the service layer, there must be a corresponding `SearchHistory` write in the `except` block before the exception propagates.

The SQLite `.db` file is a runtime artifact. It must never be committed to the repository. The `.gitignore` already excludes it — do not remove that exclusion.

Do not use `try/except Exception` as a catch-all. Each exception type that can occur has a name and maps to a specific HTTP status code. Broad catches hide bugs and produce meaningless error responses.

### Test Requirements

Any new route endpoint requires a corresponding pytest test. Any new service method that changes behavior requires a test. The test must use `TestingConfig` which uses an in-memory SQLite database — it must never connect to the development database.

When mocking the scraper in tests, always patch at `app.services.MarketplaceScraper.scrape`. Patching at the wrong import path means the mock doesn't intercept the real call.

### Logging

Log three events for every compare operation: search started (before the scrape), search succeeded (after successful scrape + DB write), search failed (in the except block, before re-raising or returning). Use `app.logger.info()` and `app.logger.error()` with an `extra={"context": {...}}` dict that always includes at minimum the URL and marketplace.

Never use `print()` for anything that should be operational. `print()` output disappears in production. Structured logs don't.

---

## 3. Security Rules

**Never expose raw Python exceptions in API responses.** A stack trace in a 500 response leaks internal structure. Every error response must use a controlled error message string.

**`SECRET_KEY` must come from the environment in any non-development setup.** The check in `__init__.py` raises a `RuntimeError` at startup if the default key is used outside debug/test mode. Do not remove this check.

**CORS is currently set to `*` for development convenience.** In any production deployment, this must be replaced with an explicit allowed-origins list. Do not treat the current CORS config as production-ready.

**All external HTTP calls must use `timeout=config["REQUEST_TIMEOUT"]`.** An unbounded request can hang indefinitely, tying up a worker thread. There are no exceptions to this rule.

---

## 4. Code Style Constraints

These aren't preferences — they're enforced by the test suite and review process:

- **Type-annotate every function signature.** Not just public methods. Every function. This is the primary form of documentation in this codebase.
- **Use `@dataclass(frozen=True)` for value objects.** `ScrapeResult` is the main example. Frozen means immutable means no subtle mutation bugs.
- **Keep functions under 40 lines.** If a function is getting long, it's doing more than one thing. Extract a private helper.
- **No abbreviations in symbol names.** Write `marketplace`, not `mktpl`. Write `alternatives`, not `alts`. Write `response`, not `resp`. The few characters saved aren't worth the cognitive load added.
- **No magic numbers or strings.** HTTP status codes should use named constants or be obvious from context. Marketplace domain strings should be defined in one place and referenced consistently.

---

## 5. How to Handle Uncertainty

If a request is ambiguous or seems to require violating one of the rules above:

1. Read `ai_docs/coding_standards.md` — it explains the engineering philosophy behind these constraints and may clarify intent.
2. Read `ai_docs/prompts.md` — it documents the decisions that shaped each part of the architecture and why certain choices were made.
3. **If the request would require violating a rule: say so and explain why, rather than complying silently.** A rule violation that's flagged can be discussed. A rule violation that slips through unnoticed leads to architectural drift.
4. When in doubt, do less. The simplest change that satisfies the requirement is almost always the right one.
