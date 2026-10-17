# NeedProof AI

### Understand the need. Verify the evidence. Improve the decision.

**NeedProof AI** is an AI-powered retail and commerce intelligence prototype that translates natural-language shopping requests into structured requirements and supports evidence-aware merchant comparison and adaptive decision-making.

Built for the **Google AI Builder Cup 2026 — Retail & Commerce** challenge, the project combines live Gemini-powered customer understanding with a full-stack merchant investigation workflow and a clearly labeled, interactive decision simulation.

**[Live Firebase Showcase](https://needproof-ai-showcase.web.app)** · **[GitHub Repository](https://github.com/shrinivashunnur08/NeedProof-AI)**

> **Important:** The live Firebase website is a standalone showcase, not the complete FastAPI-backed system. It uses live Gemini for intent extraction and fictional merchant offers for decision demonstrations. No real stock, merchant identity, delivery promise, or purchase is verified by the public demo.

## New: the Gemini commerce loop (`/app`)

**Shopper asks in any language → a Gemini agent checks nearby shops with the NeedProof decision engine → if nothing is confirmed, the need goes to shops → a shop replies with a photo that Gemini Vision checks → unanswered needs become demand insights for shops.**

- **Shopper agent:** Gemini function calling over the existing 17C–17E engine (orchestration, Evidence Passport, Next-Best-Proof). Works in English, Chinese, Portuguese, Hindi and more; budgets in any currency.
- **Shop photo proof:** Gemini Vision reads the box or label; code checks wattage, connector, USB PD, price and authenticity cues against the request.
- **Demand intelligence:** unmet demand by city and product, a 7-day estimate, a Gemini-written weekly brief, and BigQuery export with BigQuery ML `ARIMA_PLUS` and BigQuery AI SQL in `infra/bigquery/`.
- **One switch for cost:** `NEEDPROOF_PROFILE=free` (Gemini API key, local analytics) or `google_full` (Vertex AI, BigQuery). `GEMINI_BACKEND=mock` runs offline.
- Demo cities: **Singapore**, São Paulo and Mumbai. Details: [`docs/COMMERCE_LOOP.md`](docs/COMMERCE_LOOP.md).

## The Problem

Finding a product is only the beginning of a reliable purchase decision. A listing or nearby-store result does not necessarily establish that the item is in stock, compatible, genuine, within the total budget, or available by the required deadline.

NeedProof AI explores a different approach: **understand the customer's constraints first, collect relevant evidence, identify uncertainty, and reconsider the decision when circumstances change.**

## How It Works

1. **Understand:** Gemini interprets a customer's request and extracts the product, budget, location, required specifications, and missing information.
2. **Discover:** The local full-stack workflow can identify candidate businesses using Google Places. Discovery does **not** prove stock availability.
3. **Investigate:** Merchant-facing flows support collection of reported product, price, stock, and compatibility evidence. Submitted evidence is not independent verification.
4. **Evaluate:** Decision logic considers constraints such as quantity, reported stock, and budget, along with outstanding evidence gaps.
5. **Adapt:** If an offer becomes unavailable or fails a constraint, the system can reconsider the remaining candidates or recommend further investigation.

### Example Customer Journey

**Customer request:** “I need a genuine 65W USB-C PD laptop charger near Thane, under ₹1,000, available today.”

- Gemini identifies the product, ₹1,000 budget, location, and requested conditions.
- The public scenario compares **TEST_STORE_A (₹899)** and **TEST_STORE_B (₹950)** using **fictional** prices and inventory.
- Initially, Store A is the provisional leader for a quantity of one.
- When Store A's stock is simulated as zero, the decision updates to Store B.
- If neither offer satisfies the modeled constraints, the system reports that **no provisional offer is eligible**.

The decision remains **advisory only**; there is no checkout or purchase authorization.

## Two Application Modes

| Capability | Live Firebase Showcase | Local Full-Stack Application |
| --- | --- | --- |
| Premium dashboard and Decision Spotlight | Yes | Yes |
| Natural-language customer intent extraction | Live Gemini via Firebase AI Logic | Gemini via Vertex AI configuration |
| Customer-based fictional merchant simulation | Yes | Separate decision demo capabilities |
| Stock-out and budget-based replanning | Browser-based fictional scenario | FastAPI decision and journey workflows |
| Google Places candidate-store discovery | Not available | Backend integration |
| Merchant-submitted evidence and verification workflows | Not available | Backend workflows; evidence is not independently guaranteed |
| Catalog, optimizer, assurance, and merchant modules | Not available | Local application modules |
| Database persistence | No backend database | SQLite by default, with optional database configuration |
| Real purchase or guaranteed inventory | No | No |

## Technology Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite 8, Tailwind CSS 4, Lucide icons |
| Backend | Python 3.12, FastAPI, Pydantic |
| AI | Google Gemini; Firebase AI Logic for the public showcase; Vertex AI integration for local backend use |
| Discovery | Google Places API integration in the backend |
| Decision intelligence | Constraint-based evaluation, OR-Tools, experimental evidence/decision models |
| Data | SQLite, SQLAlchemy, Alembic migrations; optional PostgreSQL/Cloud SQL support in code |
| Firebase security | Firebase App Check with reCAPTCHA Enterprise |
| Hosting | Firebase Hosting (public static showcase); FastAPI runs separately for local full-stack development |
| Packaging | Dockerfile for a containerized full-stack build |

## Architecture

**Public showcase (currently deployed)**

Customer browser → React dashboard → Firebase AI Logic + App Check → Gemini intent extraction

Extracted intent → Explicitly fictional merchant offers → Browser-side constraint evaluation → Decision Spotlight and stock-out replanning

**Local full-stack workflow**

Customer browser → React/Vite → FastAPI → Gemini / Google Places / evidence and decision APIs → SQLite

The Firebase Hosting deployment does **not** run the Python API, database migrations, or merchant verification services. These remain part of the separate local full-stack application.

## Repository Structure

- `frontend/` — React application, dashboard components, Gemini Firebase showcase, styles, and frontend build configuration.
- `frontend/src/FreeShowcase.tsx` — Firebase-only customer understanding and fictional decision demonstration.
- `frontend/src/App.tsx` — Main application and routing between full-stack and showcase modes.
- `backend/app/` — FastAPI routes, models, business logic, Gemini integration, and decision workflows.
- `backend/migrations/` — Alembic database migrations.
- `backend/requirements.txt` — Python dependencies.
- `backend/.env.example` — Sample local backend configuration without actual credentials.
- `firebase.json` and `.firebaserc` — Firebase project and Hosting configuration.
- `Dockerfile` — Multi-stage React build and FastAPI runtime definition.

## Run the Complete Application Locally (Windows CMD)

**Prerequisites:** Git, Node.js 22+, Python 3.12, and access to the Google services required by any live AI/Places features you plan to use.

**1. Clone the repository**

`git clone https://github.com/shrinivashunnur08/NeedProof-AI.git`

`cd NeedProof-AI`

**2. Set up the Python backend**

`cd backend`

`py -3.12 -m venv .venv`

`.venv\Scripts\activate`

`python -m pip install -r requirements.txt`

`copy .env.example .env`

Edit `backend/.env` for your own environment. The example defaults to local SQLite. Vertex AI and Google Places operations require their respective credentials, enabled services, and appropriate access; do not commit secrets.

Apply migrations and start FastAPI:

`alembic upgrade head`

`uvicorn app.main:app --reload --port 8000`

Backend: **http://127.0.0.1:8000** · Interactive API docs: **http://127.0.0.1:8000/docs**

**3. Start the React frontend in a second CMD window**

From the repository root:

`cd frontend`

`npm ci`

`npm run dev`

Frontend: **http://localhost:5173**

Vite forwards local `/api` requests to FastAPI on port 8000. The local application runs in full-stack mode unless `VITE_PUBLIC_SHOWCASE` is explicitly enabled in the active Vite environment.

## Firebase Showcase Deployment

The public demo is built as a static frontend using Firebase Hosting and Firebase AI Logic. To deploy your **own** instance, register a Firebase web app, enable the supported Gemini backend, configure App Check and authorized domains, and create `frontend/.env.production.local` with your own values:

- `VITE_PUBLIC_SHOWCASE="true"`
- `VITE_FIREBASE_API_KEY="YOUR_WEB_API_KEY"`
- `VITE_FIREBASE_AUTH_DOMAIN="YOUR_PROJECT.firebaseapp.com"`
- `VITE_FIREBASE_PROJECT_ID="YOUR_PROJECT_ID"`
- `VITE_FIREBASE_APP_ID="YOUR_FIREBASE_APP_ID"`
- `VITE_FIREBASE_MESSAGING_SENDER_ID="YOUR_SENDER_ID"`
- `VITE_APPCHECK_SITE_KEY="YOUR_RECAPTCHA_ENTERPRISE_SITE_KEY"`

Build from `frontend/` using `npm ci` and `npm run build`, then deploy from the repository root with `firebase deploy --only hosting --project YOUR_FIREBASE_PROJECT_ID`.

**Do not commit `.env` files, service-account credentials, private API secrets, or local databases.** Firebase web app configuration is client-visible; it is not a replacement for server-side secret storage or service-level access controls.

The existing public project uses Firebase's Spark plan. Free tiers and API quotas are subject to Google's terms and may change; an unrelated billing-enabled Google Cloud project is not covered by the Spark plan.

## Quality Checks

- Frontend production build: `npm run build` (run in `frontend/`).
- Frontend linting: `npm run lint` (run in `frontend/`).
- Backend tests: `python -m pytest` (run in `backend/`).
- Local health check: **http://127.0.0.1:8000/api/health** once FastAPI is running.

The project is a hackathon prototype. A passing build and demo do not establish production-grade merchant verification, payments readiness, or independent accuracy of AI-extracted requirements.

## Responsible Use and Limitations

- **No fabricated merchant certainty:** Google Places discovery finds candidate businesses, not guaranteed inventory.
- **Evidence is reported, not independently verified:** Merchant submissions may be incomplete, inaccurate, or outdated.
- **Simulation is explicitly fictional:** TEST_STORE_A and TEST_STORE_B are invented merchants; synthetic prices are not quotations.
- **Provisional decisions only:** The recommendation engine does not authorize purchases or guarantee delivery, compatibility, authenticity, or refunds.
- **No real checkout:** Payment execution is not implemented in the public showcase.
- **Service availability varies:** Live Gemini requests depend on model access, quotas, App Check configuration, and network responsiveness.

## Project Status

**Hackathon prototype — active development.** The public Firebase showcase is deployed, with live Gemini extraction and an interactive fictional decision journey. The broader backend-driven commerce investigation features are available in the local project and are not all hosted publicly.

## Author

Developed by **Shrinivas Hunnur** for the **Google AI Builder Cup 2026**.

GitHub: **[@shrinivashunnur08](https://github.com/shrinivashunnur08)**

## License

No open-source license has been specified for this repository. All rights are reserved by default unless a license is added.
