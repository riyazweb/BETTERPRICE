# PricePulse Assessment

PricePulse is a small, production-style price comparison product built for this assessment using Flask (API), React (UI), and SQLite (relational database).

This submission is created specifically for this assessment and does not include confidential, proprietary, or employer-owned code, data, or prompts.

## Repository Structure

```text
/PricePulse-Assessment
├── /backend
│   ├── /app
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── services.py
│   ├── /tests
│   │   └── test_api.py
│   ├── config.py
│   ├── pytest.ini
│   ├── requirements.txt
│   └── run.py
├── /frontend
│   ├── /src
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   └── vite.config.js
├── /ai_docs
│   ├── coding_standards.md
│   └── prompts.md
├── AGENTS.md
├── .gitignore
└── README.md
```

## Stack (Required)

- Backend: Python + Flask
- Frontend: React (Vite)
- Database: SQLite (SQLAlchemy ORM)
- Tools: Pydantic, Requests, BeautifulSoup, Pytest, TailwindCSS

## Key Technical Decisions

1. Flask Application Factory (`create_app`) for testability and clean setup.
2. Service layer abstraction (`BaseScraper`, `PriceComparisonService`) to isolate scraping logic from routes.
3. Strict request/response contracts with Pydantic (`extra="forbid"`) for interface safety.
4. Structured JSON logging + `SearchHistory` persistence for observability.
5. Explicit typed error mapping for correctness and predictable API behavior.

## End-to-End Flow (How It Works)

1. User pastes a product URL in frontend UI and clicks Compare.
2. Frontend sends `POST /api/v1/compare` with `{ "url": "..." }`.
3. Backend validates input with `PriceRequest` (URL format, supported domain, no extra fields).
4. Service layer scrapes and normalizes product + alternatives data.
5. Backend validates response with `ProductResponse` before returning JSON.
6. Search is logged to DB in success and failure paths.
7. Frontend renders image, current price, comparison graph, and seller cards.

## Features Included

- URL validation and marketplace detection (Amazon, Flipkart)
- Main product image + thumbnail preview
- Centered current price section
- Price comparison graph
- Seller list with sort (Lowest/Highest)
- Best deal badge + savings insight + confidence indicators
- History endpoint + history panel
- Copy URL and shareable link support (`?url=...`)
- Friendly error toasts for API/network/copy failures

## Setup and Run (Install to End)

## 1) Prerequisites

- Python 3.10+
- Node.js 18+
- npm

## 2) Backend Setup

```bash
cd backend
python -m pip install -r requirements.txt
python run.py
```

Backend base URL:

- `http://127.0.0.1:5000/api/v1`

## 3) Frontend Setup

Open a new terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

- `http://127.0.0.1:5173`

Notes:

- Vite proxy forwards `/api/*` to backend (`127.0.0.1:5000`).
- Optional direct backend mode can use `VITE_API_BASE_URL` from `frontend/.env.example`.

## 4) Run Tests

```bash
cd backend
python -m pytest -q
```

Current status: **11 tests passing**.

## 5) Production Build Check (Frontend)

```bash
cd frontend
npm run build
```

## API Reference

## Health

- `GET /api/v1/health`
- Response: `{ "status": "ok" }`

## Compare

- `POST /api/v1/compare`
- Request body:

```json
{
  "url": "https://www.amazon.in/dp/B0ABCDE123"
}
```

- Success response (example):

```json
{
  "title": "Sample Product",
  "price": 1499.0,
  "image_url": "https://...",
  "thumbnail_images": [],
  "source": "buyhatke",
  "marketplace": "amazon",
  "tracker_url": "https://...",
  "alternatives_count": 3,
  "alternatives": [],
  "status": "Success",
  "error": null
}
```

## History

- `GET /api/v1/history`
- Returns latest search entries (success and failure).

## Error Handling

- 400: Validation failures / unsupported input
- 404: Upstream not found
- 503: Timeout or bot-block
- 502: Other scraper errors

## Architecture Quality (What Reviewers Evaluate)

- Structure: clear boundaries (`routes` → `services` → `models`/`schemas`)
- Simplicity: readable, explicit code paths
- Correctness: invalid states rejected early
- Interface Safety: strict schema validation on request and response
- Change Resilience: scraper adapter pattern; route contract remains stable
- Verification: automated pytest suite
- Observability: structured logs + persisted search history
- AI Guidance: documented constraints and prompting artifacts
- AI Usage: generated code reviewed and corrected where needed

## AI Guidance Files

- `AGENTS.md`
- `ai_docs/coding_standards.md`
- `ai_docs/prompts.md`

## Risks and Mitigations

1. Marketplace HTML/API changes
   - Mitigation: isolate scraping logic in service layer.
2. Upstream timeout or bot detection
   - Mitigation: explicit error mapping + persisted failure records.
3. Bad user input
   - Mitigation: strict Pydantic validation with `extra="forbid"`.

## Extension Plan

- Add new marketplace adapters as new `BaseScraper` classes
- Add caching for repeated requests
- Add async queue + retries for scrape jobs
- Add auth/rate limiting for production
- Add tracing/metrics for deeper monitoring

## Submission Checklist Mapping

| Requirement | Status | Evidence |
|---|---|---|
| Flask backend | ✅ | `backend/app/` |
| React frontend | ✅ | `frontend/src/App.jsx` |
| Relational DB | ✅ | SQLite + SQLAlchemy (`SearchHistory`) |
| Working repository | ✅ | App runs, tests pass, build passes |
| Key technical decisions | ✅ | This README section |
| Walkthrough content | ✅ | Flow, risks, extension plan sections |
| AI guidance files | ✅ | `AGENTS.md`, `ai_docs/*` |
| Verification | ✅ | `backend/tests/test_api.py` (11 passing) |
| Observability | ✅ | structured logs + DB history |

## Quick Commands

```bash
# Backend
cd backend
python -m pip install -r requirements.txt
python run.py

# Backend tests
python -m pytest -q

# Frontend
cd ../frontend
npm install
npm run dev

# Frontend production build
npm run build
```
