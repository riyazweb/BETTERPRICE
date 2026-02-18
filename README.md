# 💰 BETTER PRICE — Price Comparison & Tracking Engine

<img width="2752" height="1501" alt="Better Price App Screenshot" src="https://github.com/user-attachments/assets/a844e7af-7bcf-48fa-93cf-dc2f685d90ce" />

**BETTER PRICE** is a high-velocity price comparison and tracking engine that lets users instantly compare prices across major marketplaces like **Amazon** and **Flipkart**. Built with a resilient, modular architecture — small, well-structured, and correct as it evolves.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python + Flask (Application Factory Pattern) |
| **Frontend** | React (Vite) + TailwindCSS |
| **Database** | SQLite via SQLAlchemy ORM |
| **Validation** | Pydantic v2 (Interface Safety) |
| **Testing** | Pytest — 11/11 tests passing ✅ |

---

## 🏗️ Architecture & Engineering Quality

This project was built following **SOLID principles** and a **Service-Oriented Architecture** to ensure the system remains *understandable and correct as it evolves* — the core evaluation criterion.

### ✅ Structure — Clear Boundaries & Logical Organization
The codebase is split into strict layers: **Routes → Schemas → Services → Models**. Each layer has a single responsibility. No business logic leaks into routes; no data access logic leaks into services.

### ✅ Simplicity — Readable, Predictable Code
Patterns are consistent and boring by design. Every route follows the same flow: validate input → call service → return response. No clever abstractions that require decoding.

### ✅ Correctness — Prevents Invalid States
All data mutations pass through **Pydantic v2 schemas** before touching the database or service layer. Invalid states are structurally impossible — not just caught at runtime.

### ✅ Interface Safety — Guards Against Misuse
Pydantic schemas use `extra="forbid"` — the API **rejects** any request with unexpected fields. This is a strict contract, not a soft suggestion.

### ✅ Change Resilience — New Features Without Widespread Impact
The scraping/data-fetching logic lives entirely in a **standalone Service Layer**. Swapping the data source (e.g., from a reverse-engineered API to an official one) requires changing **one file**. Zero cascade.

### ✅ Verification — Automated Tests Proving Correctness
A full test suite covers URL validation, data extraction, schema enforcement, and error paths. Tests are the final guarantee that behavior stays correct after every change.

```bash
cd backend && python -m pytest
# 11 passed in X.XXs ✅
```

### ✅ Observability — Failures Are Visible & Diagnosable
Every search — success or failure — is persisted to the SQLite database with structured JSON logs, including timestamps, query inputs, and error states. Failures never disappear silently.

---

## 💡 Key Technical Decisions

### 1. Reverse-Engineered API over HTML Scraping
**Decision:** Instead of building fragile HTML scrapers (which get blocked and break on DOM changes), I reverse-engineered a commercial price-aggregator API.

**Tradeoff:** This trades long-term control for immediate reliability. The demo is 100% stable, but the upstream API is a dependency I don't own.

**Mitigation:** The Service Layer abstraction means if this API changes or goes down, the fix is localized to one service file — no routes, models, or frontend code changes.

### 2. Flask Application Factory (`create_app`)
**Decision:** Used the Application Factory pattern instead of a global `app` instance.

**Why:** Enables clean test isolation (each test gets a fresh app context), supports multiple environment configs, and prevents circular import issues as the app grows.

### 3. SQLite for the Assessment Scope
**Decision:** SQLite over PostgreSQL/MySQL.

**Why:** Zero-dependency setup for reviewers. The SQLAlchemy ORM means swapping to PostgreSQL for production requires changing **one connection string**.

### 4. Pydantic `extra="forbid"` Contracts
**Decision:** All schemas reject unexpected fields at the boundary.

**Why:** This enforces the API contract strictly. It prevents subtle bugs where extra data silently passes through and corrupts downstream logic.

---

## ✨ Features

- 🔍 **Smart URL Detection** — Automatically identifies Amazon or Flipkart product links
- ⚡ **Live Price Comparison** — Fetches real-time prices, images, and ratings
- 📈 **Price History Graph** — Visualizes price trends over time
- 🔃 **Advanced Sorting** — Filter alternative sellers by lowest or highest price
- 📋 **Search History** — Persistently tracks previous searches per session
- 🚨 **Graceful Error Handling** — Toast notifications for timeouts, invalid links, and API failures

---

## 🤖 AI Usage & Guidance

This project follows an **AI-First engineering model**. AI was used as a **force multiplier**, not a code dispenser.

### How AI Was Used
- **Scaffolding:** Initial route and model boilerplate was AI-generated
- **Refactoring:** AI was prompted to refactor a monolithic prototype into the Service-Layer architecture
- **Test Generation:** AI generated initial test cases, which were then critically reviewed and extended

### How AI Was Constrained (see `/ai_docs`)
The `/ai_docs` folder contains the exact instruction files used to guide AI agents:

- **No route is shipped without an associated Pydantic schema** — AI was instructed to treat unvalidated routes as broken
- **No feature is shipped without a test** — AI was blocked from marking tasks complete without a corresponding test case
- **Monolithic code is rejected** — AI was instructed to separate concerns into the defined layer structure

### Critical Review Process
The AI's first output was a single-file Flask app. I **rejected it**, identified the architectural violations, and re-prompted with explicit constraints. The final structure is the result of that review loop — not the first output.

---

## 🚀 Setup & Run

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Backend
```bash
cd backend
pip install -r requirements.txt
python run.py
```
> Runs at: `http://127.0.0.1:5000`

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
> Runs at: `http://127.0.0.1:5173`

### 3. Run Tests
```bash
cd backend
python -m pytest
```
> Expected: **11 passed** ✅

---

## 📁 Repository Structure

```text
better-price/
├── backend/
│   ├── app/
│   │   ├── models/         # SQLAlchemy DB Models
│   │   ├── schemas/        # Pydantic v2 Validation Schemas
│   │   ├── services/       # Business Logic & Data Fetching
│   │   └── routes/         # Flask Route Handlers
│   ├── tests/              # Pytest Suite (11 tests)
│   └── run.py              # Application Entry Point
├── frontend/               # React + Vite + TailwindCSS
├── ai_docs/                # AI Coaching Files & Coding Standards
└── README.md
```

---

## ⚠️ Risks, Weaknesses & Extensions

### Known Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Upstream API changes break data extraction | Medium | Service Layer isolates the change to one file |
| SQLite not suitable for concurrent production load | Low (assessment scope) | ORM swap to PostgreSQL = one connection string change |
| No rate limiting on endpoints | Medium | Add `Flask-Limiter` as a one-file addition |

### Honest Weaknesses
- The reverse-engineered API is an external dependency I don't control — a terms-of-service risk in production
- No user authentication in this version — search history is global, not per-user
- Price history is limited by how often users search, not by a background polling job

### Future Extensions
1. **User Authentication** — JWT-based auth to scope history per user
2. **Price-Drop Alerts** — Background Celery task + email notifications via SendGrid
3. **International Marketplaces** — Plugin architecture in the Service Layer to add new scrapers
4. **Background Polling** — Scheduled price refresh for tracked products without user-triggered searches

---

*Built specifically for the Better Software Associate Software Engineer assessment. No confidential, proprietary, or employer-owned code was used.*
