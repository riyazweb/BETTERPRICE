# AGENTS.md — AI Agent Constraints for PricePulse

This file constrains how any AI agent (Copilot, Claude, Cursor, etc.) may contribute to this codebase.
All generated code **must** comply with these rules before being accepted.

---

## 1. Scope of Permitted Changes

| Layer | Permitted | Forbidden |
|-------|-----------|-----------|
| `routes.py` | Add/change endpoints; map new error types | Touch scraper logic, embed business rules |
| `services.py` | Add new `BaseScraper` implementations; extend `PriceComparisonService` | Alter the public `compare()` interface signature |
| `schemas.py` | Add fields; tighten validators | Remove validators; allow `extra="allow"` |
| `models.py` | Add columns; add indexes | Drop columns or tables; rename without migration |
| `tests/` | Add tests for new behavior | Remove or weaken existing assertions |
| `frontend/src/` | Add UI features | Remove error boundary logic or loading state |

---

## 2. Non-Negotiable Constraints

### Interface Safety
- Every request body **must** be validated through a Pydantic schema with `extra="forbid"`.
- Every response **must** be validated through `ProductResponse.model_validate()` before `jsonify()`.
- URL domain validation via `detect_marketplace()` must run before any network call.

### Change Resilience
- Route handlers must **never** import from `beautifulsoup4`, `requests`, or any HTTP client directly.
- All scraping logic lives exclusively in a `BaseScraper` subclass inside `services.py`.
- Adding a new marketplace adapter requires **only** a new class in `services.py` — zero route changes.

### Correctness
- `SearchHistory` must be written for **every** `/compare` call — both success and failure paths.
- Do not use `try/except Exception` broad catches; map each error type explicitly.
- Never commit the SQLite `.db` file; it is a runtime artifact only.

### Verification
- Any new route or service method **requires** a corresponding pytest test.
- Tests must use the `TestingConfig` in-memory SQLite database — never the development database.
- Mock `MarketplaceScraper.scrape` at the patch target `app.services.MarketplaceScraper.scrape`.

### Observability
- Log every search start, success, and failure through `app.logger` with a `context` dict.
- Never use `print()` for operational logging.

---

## 3. Security Rules

- Do not expose raw Python exceptions or stack traces in API responses.
- The `SECRET_KEY` must come from the environment — never hardcode it for production.
- CORS is `*` for development only; a production deployment must restrict it.
- All external HTTP calls must use `timeout=config["REQUEST_TIMEOUT"]` — no unbounded requests.

---

## 4. Code Style

- Type-annotate all function signatures in Python files.
- Use `@dataclass(frozen=True)` for value-object return types (e.g., `ScrapeResult`).
- Keep individual functions under 40 lines; extract helpers if exceeded.
- No abbreviations in symbol names (`marketplace` not `mktpl`, `alternatives` not `alts`).

---

## 5. What to Do When Uncertain

1. Read `ai_docs/coding_standards.md` for engineering philosophy.
2. Read `ai_docs/prompts.md` for the prompt history that shaped this architecture.
3. If the request violates any rule above, **refuse and explain** rather than comply silently.
4. Prefer the simplest solution that satisfies the requirement — do not add features not asked for.
