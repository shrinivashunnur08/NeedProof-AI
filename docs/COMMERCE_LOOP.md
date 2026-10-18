# Commerce loop: Gemini agent, photo proof and demand insights

**Route:** `http://127.0.0.1:5173/app` · **API:** `/api/v2/loop/*` · **Code:** `backend/app/commerce_loop/`, `frontend/src/loop/`

## The loop

1. **Shopper (any language).** A Gemini agent with function calling understands the need, calls
   `find_offers` (shop listings in the city, each run through the 17C orchestration, 17D Evidence Passport and
   17E Next-Best-Proof engine plus a spec check), and, when nothing is usable or photo-verified, calls
   `ask_nearby_shops`. Shop names, prices and decision states come from code; Gemini chooses tools and explains.
2. **Shop.** The request appears in every nearby shop's inbox. A shop replies with a photo ("send a shelfie").
   Gemini Vision extracts brand, wattage, connector, USB PD, price and authenticity cues into a typed claim;
   deterministic code compares it with the request: `PHOTO_MATCHES_REQUEST`, `PHOTO_CONFLICTS_WITH_REQUEST`,
   `PHOTO_NEEDS_CLEARER_DETAIL` or `PHOTO_UNREADABLE`. The shopper's view updates within seconds.
3. **Business.** Every request is a demand event. Unanswered requests become unmet demand per city and product,
   with a 7-day estimate and a Gemini-written weekly brief in English, Chinese, Portuguese or Hindi.
   Events export to BigQuery; `infra/bigquery/` has the view, the BigQuery ML `ARIMA_PLUS` forecast and an
   `AI.GENERATE` brief for the full Google profile.

Cities: Singapore (S$), São Paulo (R$), Mumbai (₹). Budgets parse in any currency (S$, R$, ₹, $, £, €, ¥, "1k",
新币, reais, रुपये). All shops, listings and seeded demand history are fictional and labelled as demo data.

## Free and full Google profiles (one switch)

| Setting | free (default) | google_full |
| --- | --- | --- |
| `GEMINI_BACKEND` | `ai_studio` (Gemini API key) | `vertex` (Gemini on Vertex AI) |
| `ANALYTICS_BACKEND` | `local` (SQLite + BigQuery sandbox export) | `bigquery` |
| Insights brief | backend calls Gemini | BigQuery AI `AI.GENERATE` (`03_bigquery_ai_brief.sql`) |
| Forecast | week-over-week estimate | BigQuery ML `ARIMA_PLUS` (`02_forecast_arima.sql`) |

Set `NEEDPROOF_PROFILE=google_full` or override each variable. `GEMINI_BACKEND=mock` runs fully offline and is
what CI uses. The header badge shows which model backend is live, so the demo never claims more than it runs.

## Run

```powershell
# backend\.env
GEMINI_BACKEND=ai_studio
GEMINI_API_KEY=<key from https://aistudio.google.com/apikey>
LOOP_GEMINI_MODEL=gemini-flash-lite-latest

cd backend; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
cd frontend; npm run dev -- --host 127.0.0.1
```

Open `/app?role=shopper&city=singapore` and, in a second window, `/app?role=shop&city=singapore`.

## Safety

- The loop never buys anything and never marks a listing as verified; photo evidence is labelled
  "AI-read shop evidence, not independent verification".
- A shop can only reply to requests in its own city. Photos are limited to 5 MB and image types.
- Shopper text and photo text are treated as data in the system prompts.
- Disabled when `ENVIRONMENT=production` unless `COMMERCE_LOOP_ENABLED=true`.

## Tests

`backend/tests/test_commerce_loop.py` (22 tests, mock model): currency parsing in seven formats, city
resolution in four scripts, agent tool flow, spec conflicts, cross-city denial, photo rules, insights, brief,
production gate and reset.
