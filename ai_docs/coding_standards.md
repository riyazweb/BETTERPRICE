# Coding Standards: PricePulse Assessment

## Intent
This system was built by coaching AI with strict engineering constraints so the codebase remains understandable, safe, and evolvable under change.

## Core Coaching Rules
1. **Interface Safety First**
   - Every external request/response must pass through Pydantic schemas.
   - Reject invalid URLs and unsupported marketplaces before service execution.
   - API responses must use a predictable contract (`title`, `price`, `image_url`, `source`, `marketplace`, `status`, `error`).

2. **SOLID by Default**
   - **Single Responsibility**: routes handle transport only, services handle business logic, models handle persistence.
   - **Open/Closed**: scraper behavior is abstracted via `BaseScraper`, enabling extension without route changes.
   - **Liskov Substitution**: any future scraper implementation can replace `MarketplaceScraper` without changing consumers.
   - **Interface Segregation**: routes depend on concise service methods and schema contracts, not scraper internals.
   - **Dependency Inversion**: `PriceComparisonService` depends on the `BaseScraper` abstraction, not a concrete parser.

3. **Change Resilience**
   - Scraping/parsing concerns are isolated in the service layer.
   - Upstream provider swap (e.g., paid API) must only require a new scraper implementation.

4. **Observability as a Release Gate**
   - Persist all searches and failures in SQLite via `SearchHistory`.
   - Emit structured logs (JSON) with contextual metadata for debugging and analytics.

5. **Verification Is Non-Negotiable**
   - Add pytest coverage for invalid input, success paths, and upstream failure handling.
   - Do not ship route changes without tests for response contract stability.

## Output Quality Constraints Used While Coaching AI
- Keep modules small and explicit.
- Avoid framework leakage into domain logic.
- Handle 404/503/timeout with explicit error mapping.
- Prefer deterministic behavior over implicit fallbacks.
- Document technical risks and future extension points.
