# NeedProof · Google AI Builder Cup 2026 submission kit

Everything below describes the app as deployed on 18 Oct 2026 at
https://needproof-822406860102.asia-southeast1.run.app (repo: https://github.com/shrinivashunnur08/NeedProof-AI).
Nothing here is a plan presented as done; future work is labelled.

---

## 1. Brief description (960 of 1,024 characters)

> NeedProof: know it's in stock before you go. A shopper asks in any language by text, voice or photo ("this shirt design, size M, under ₹1500, near Wadala"). Gemini 2.5 Flash-Lite on Vertex AI reads the photo and request and picks the kind of shop that sells it; the request reaches real nearby shops found with the Google Places API. A shop replies with one photo from its inbox or a one-tap WhatsApp link, no app needed; Vertex AI Search finds the item in its uploaded stock and Gemini drafts a reply a person approves. Gemini Vision reads the shop's photo and code checks design, size, specs and brand, so the shopper goes only where the item is proven, with directions. Every request feeds demand analytics: shops see missed sales, stock cover and forecasts from their own data; managers see demand by category with BigQuery ML forecasts and a BigQuery AI brief. Runs on Cloud Run; photos and app state in Cloud Storage. Firebase and Firestore are not used.

## 2. How each Google technology is used (exact)

| Technology | What it does in NeedProof | Where in code |
|---|---|---|
| **Gemini 2.5 Flash-Lite on Vertex AI** (service account, no API key) | 1) reads the shopper's reference photo; 2) extracts intent (item, colour, size, budget, place, language) in any language; 3) picks the shop category (up to two) for routing; 4) runs the agent with function calling over `find_offers`, `ask_nearby_shops`, `plan_basket`; 5) reads each shop's reply photo (item, design, size, specs, brand, price); 6) drafts shop replies from real stock rows; 7) writes the answer and the shop's weekly advice in the user's language | `snap.py`, `intent.py`, `agent.py`, `gemini.py`, `vision.py`, `inventory.py`, `myshop.py` |
| **Vertex AI Search** (data store `needproof-inventory`) | Finds the requested item in a shop's uploaded stock before Gemini drafts the reply | `vertex_search.py`, `inventory.py` |
| **BigQuery** (dataset `needproof_loop`) | Demand events, unmet-demand and daily-demand views | `bigquery_loop.py` |
| **BigQuery ML** | ARIMA_PLUS forecast of requests per product (next 7 days, 90% interval) | `bigquery_loop.py` |
| **BigQuery AI** | `AI.GENERATE` writes a demand brief inside BigQuery over the unmet-demand view | `bigquery_loop.py` |
| **Cloud Run** (`needproof`, asia-southeast1) | One container serves the React app and FastAPI API; server-checked roles, rate limit, daily AI cap | `Dockerfile`, `api.py`, `guard.py`, `access.py` |
| **Cloud Build** | Builds the container from source on each deploy | `gcloud run deploy --source .` |
| **Cloud Storage** | Shopper and shop photos (private, served by the backend); snapshots of the app database so redeploys keep data | `media.py`, `persist.py` |
| **Maps Platform** | Places API (New): open shops by category with rating, phone and Maps link; Geocoding: place names; Maps Static: the shop map | `discovery.py`, `LoopApp.tsx` |
| **Looker Studio** | A report link on the BigQuery views is prepared; it must be saved once by the project owner | `docs/GOOGLE_CLOUD.md` |
| **Firebase / Firestore** | **Not used.** Operational data is SQLite inside Cloud Run, snapshotted to Cloud Storage | — |

## 3. USP (one line)

**Proof, not promises.** Before you travel, a real nearby shop shows the exact item with one photo, and Gemini checks it matches what you asked for.

## 4. Business value

- **Shoppers:** no wasted trips or phone calls; they compare proof, not listings.
- **Neighbourhood shops:** a ready-to-buy customer at zero setup (no app, no catalogue, no account), plus demand they never saw: what people asked for, what they missed, at what budgets.
- **Businesses and malls:** demand by category and neighbourhood, forecasts and missed-sales data from real requests.
- **Model:** free for shoppers; shops pay per ready-to-buy customer or a monthly insights plan; category demand sold to brands and malls (proposal, not tested).
- **Unit cost (estimate at list prices):** about US$0.01 per request at a 10,000-request pilot, mostly Maps search. See the deck's cost slide.

## 5. Demonstrated today vs future

| Demonstrated in the live app | Future (not built) |
|---|---|
| Text, voice and photo search in several languages | WhatsApp Business API (shops reply inside WhatsApp) |
| Gemini routing to one or two shop categories; real shops from Google Places | Restock notifications to shoppers |
| One-photo reply from inbox or signed WhatsApp link; Gemini Vision check with match/conflict reasons | Shop trust score from proof history |
| AI reply drafts from uploaded stock (Vertex AI Search + Gemini), human approval | Cloud SQL / AlloyDB and multiple Cloud Run instances |
| Directions and Google Maps links for replying shops | Firebase Authentication (today: role dropdown, server-checked) |
| Shop dashboard from its own data; sales upload → forecast, customer groups, basket rules | Looker dashboards (today: Looker Studio link only) |
| Business routing table, BigQuery ML forecast, BigQuery AI brief | Field pilot with real shops and measured outcomes |
| Trust report: live tests, safeguards, benchmarks | |

Known limits to state openly: the three "sample" shops per city are fictional and labelled; live tests are small (19 cases, synthetic label photos); benchmarks are seeded simulations; Google's own shop categories are sometimes wrong (a salon listed as a grocery); Gemini latency varies (7–9 s typical for a photo search, slower at times).

---

## 6. Video: 3 min 30 s, two presenters

**Setup before recording** (15 minutes before):
1. Open the app as **Admin / jury**, press **Reset data**, then pick **Mumbai**.
2. Window 1 (shopper): `…/?as=shopper&role=shopper&city=mumbai`. Run one throwaway request to warm up Gemini, then press **New conversation**.
3. Close all other app tabs. Record at 1280×800 or larger, browser zoom 100%.
4. Tell Claude/your teammate not to redeploy during recording.
5. Never press the green **WhatsApp** button on camera (it would message a real shop). Use **Reply as shop**.

| Time | Who | Screen and action | Say (exact) | Expected on screen |
|---|---|---|---|---|
| 0:00–0:15 | **A** | Shopper home, Mumbai | "You need one specific thing today: a navy shirt in this exact print, size M. Which shop near you actually has it? Today you call around or walk in and hope." | Role bar shows **Shopper** |
| 0:15–0:30 | **A** | Point at the role bar | "NeedProof asks real nearby shops to prove it with one photo, and Gemini checks the proof. I'm the shopper; my teammate will be the shopkeeper." | — |
| 0:30–0:55 | **A** | Tap **📷 Search by photo: this shirt design**. Type: *size M, under ₹1500, near Wadala*. Press **Ask** | "I just show it the shirt. Gemini reads the photo, I add size, budget and place." | "From your photo: a navy blue shirt with a white floral print…", then the request |
| 0:55–1:20 | **A** | Scroll: **What I understood**, **Real shops nearby**, map | "Gemini understood item, budget and place, decided this needs a clothing shop, and sent it only to real clothing shops near Wadala from Google Maps — each with its rating, Maps link and directions." | Intent chips; list of real shops with **Google Maps**, **Directions**, **Reply as shop** |
| 1:20–1:50 | **B** | Click **Reply as shop ↗** on the first shop → new window | "I'm that shop. No app, no catalogue: I see the request and the shopper's photo. I take one photo of what I have — here, our navy floral shirt — and send it at ₹1,299." Click **Navy floral shirt** sample, enter price 1299, **Send photo proof** | **Gemini Vision analysis: Photo matches the request** — same design, size M |
| 1:50–2:10 | **B** | Back in shopper window click **Reply as shop** on the second shop; choose **Red check shirt**, price 999, send | "A second shop sends a different shirt. Gemini reads it and the code compares it with what the shopper asked." | **Photo conflicts with the request**: colour red not navy, pattern checked not floral |
| 2:10–2:30 | **A** | Shopper window: request tracker | "Both answers arrive live. One proven match, one conflict, with reasons. I tap Get directions and go to the shop that proved it." Click **Get directions** (Google Maps opens) | Two replies with photos, prices, **Real shop · Google Places**, **Get directions** |
| 2:30–2:50 | **B** | Shopkeeper window → **My shop: stock, demand, sales** | "For the shop, every request is data: requests for its kind of shop, what it answered, and items people asked for that it doesn't stock. Upload a stock sheet and AI drafts replies; upload sales and it forecasts." | Requests count, outcomes bar, missed sales |
| 2:50–3:10 | **B** | Role → **Business manager** → Business tab | "Across the city, requests are routed by category, and BigQuery ML forecasts demand; BigQuery AI writes the brief." Click **Write brief with BigQuery AI** | Routing table; BigQuery ML forecast table; brief bullets |
| 3:10–3:22 | **A** | Role → **Admin / jury** → **Trust report** | "Gemini understands and reads photos; code and our decision engine decide. Live tests pass 19 of 19 on Vertex AI, and the safeguards are listed here." | Pipeline, live model tests, safeguards |
| 3:22–3:30 | **A + B** | Back to shopper tracker | A: "Proof, not promises." B: "Built on Gemini on Vertex AI, Vertex AI Search, BigQuery, Cloud Run and Google Maps." | — |

**Omit on purpose:** basket optimiser, EVSI planner, inventory upload, sales upload, engine details — they slow the story.

**Contingency (never fake an output):**
- *Gemini slow (>15 s):* keep talking over the spinner; if it errors, say "retrying" and press Ask again. Record each scene separately and cut between takes; never replace a live result with a mock-up.
- *A shop reply returns a different verdict than expected:* show it as is and say what Gemini saw; or redo the take.
- *BigQuery AI brief fails or is slow:* skip the click and show the forecast table only.
- *Places returns few shops:* the agent falls back to OpenStreetMap; continue.
- *Location:* if the app shows "City centre", the request text "near Wadala" still sets the place.

---

## 7. Final submission checklist

- [ ] Deck PDF under 5 MB (`NeedProof_AI_Builder_Cup.pdf` is ~1.7 MB). Fill team name and leader on slide 1, video link on slide 14, then export again.
- [ ] Video 3–4 minutes, uploaded (YouTube unlisted or Drive "anyone with the link"), link pasted in the deck and form.
- [ ] Live prototype opens in a private window without sign-in: https://needproof-822406860102.asia-southeast1.run.app
- [ ] Repo public: GitHub → Settings → General → Change visibility → Public. `main` contains the merged code (done 18 Oct).
- [ ] Description (section 1) pasted in the form.
- [ ] Cloud Run stays up through judging (min instances 1, budget alert ₹900). No redeploys during judging.
- [ ] After judging: rotate the Gemini API key used locally, delete Maps keys, set min instances to 0, run the teardown in `docs/GOOGLE_CLOUD.md`.

---

## 8. Jury review (senior panel view) and what was changed

| Criterion | Verdict | Notes / fixes made |
|---|---|---|
| Originality | Strong | Per-request photo proof from real shops, checked by a model, is uncommon; the "no app for shops" path is credible for Indian neighbourhood retail. |
| Functional depth | Strong | Full loop works live: ask → route → real shops → reply → check → directions → analytics. |
| AI and Google usage | Strong, honest | Gemini in seven places with clear division of labour (model reads, code decides). BigQuery ML/AI and Vertex AI Search are real but secondary; deck says so. AlloyDB/Cloud SQL not used — stated. |
| Technical execution | Good | 546 tests, live e2e. Risks: single instance; Gemini latency spikes (timeout + retry added on 18 Oct). |
| Business impact | Medium–strong | Clear value; no field data yet. Deck labels the business model as a proposal and the pilot as future. |
| Evidence | Honest but thin | Small eval set and simulated benchmarks; deck labels them. Strongest evidence is the live demo itself. |
| Storytelling | Strong if the video follows one shirt from ask to directions | Fixed: sample prices in ₹ for Mumbai, reply price shown as ₹1,299, nearby-shop list readable. |

Weak spots a judge may probe, with honest answers:
- *"Are these real shops?"* Yes, from Google Places (open businesses only). Three per city are labelled sample shops.
- *"What if a shop sends an old photo?"* Gemini checks it matches the request, not that it is new; next step is a shop trust score and live-photo capture.
- *"Why not Firestore/Cloud SQL?"* Single-instance SQLite with Cloud Storage snapshots was enough for the prototype; Cloud SQL is the first platform step.
