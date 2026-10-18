# NeedProof on Google Cloud

Two profiles share one codebase. `free` (default) runs on a laptop with a Gemini API key.
`google_full` runs on Google Cloud. The switch is environment variables only.

| Piece | `free` profile | `google_full` profile (deployed) |
|---|---|---|
| Gemini (intent, agent, vision, drafts) | Gemini API key, `gemini-flash-lite-latest` | **Vertex AI**, `gemini-2.5-flash-lite`, no API key (service account) |
| Demand analytics | SQLite + week-on-week estimate | **BigQuery** dataset `needproof_loop` in `asia-southeast1` (Singapore) |
| Forecast | 14B.1 backtested baselines | plus **BigQuery ML ARIMA_PLUS** (`needproof_loop.demand_forecast`) |
| Shop brief | Gemini in the backend | plus **BigQuery AI** `AI.GENERATE` over the `unmet_demand` view |
| Inventory search | Local rules | **Vertex AI Search** (data store `needproof-inventory`), then the same rules |
| Shop photos | Local disk | **Cloud Storage** bucket (private, served by the backend) |
| Hosting | `uvicorn` + Vite | **Cloud Run** `needproof` in `asia-southeast1`, built by **Cloud Build** |
| Dashboard | Business tab | plus **Looker Studio** on the BigQuery views |
| Spend control | none needed | Budget alert (₹900 ≈ US$10), per-visitor rate limit, daily AI cap, max 1 instance |

## Deployed resources (project `project-e191c6db-1912-4df5-acf`)

- Cloud Run service `needproof` (asia-southeast1), service account `needproof-run@…`, max 1 instance, min 0.
- Service account roles: Vertex AI User, BigQuery Job User + dataset writer, BigQuery Connection User,
  Discovery Engine Editor (Vertex AI Search), Storage Object Admin on the media bucket, Log Writer.
- BigQuery: dataset `needproof_loop` (tables/views `demand_events`, `unmet_demand`, `daily_demand`,
  model `demand_forecast`), connection `asia-southeast1.vertex_conn` for `AI.GENERATE`.
- Vertex AI Search: data store `needproof-inventory`, engine `needproof-inventory-search` (global).
- Cloud Storage: `gs://needproof-media-822406860102` (uniform access, public access prevented).
- Budget: "NeedProof demo cap", ₹900 with email alerts at 50/90/100 %. Alerts do not stop spending.

## Cloud Run environment

```
ENVIRONMENT=production
COMMERCE_LOOP_ENABLED=true
NEEDPROOF_PROFILE=google_full
GEMINI_BACKEND=vertex
GOOGLE_CLOUD_PROJECT=project-e191c6db-1912-4df5-acf
GOOGLE_CLOUD_LOCATION=global
LOOP_GEMINI_MODEL=gemini-2.5-flash-lite
ANALYTICS_BACKEND=bigquery
BIGQUERY_LOCATION=asia-southeast1
BIGQUERY_CONNECTION=asia-southeast1.vertex_conn
BIGQUERY_AI_MODEL=gemini-2.5-flash
MEDIA_STORE=gcs
MEDIA_BUCKET=needproof-media-822406860102
INVENTORY_SEARCH=vertex
LOOP_RATE_LIMIT=true
LOOP_RATE_PER_MIN=20
LOOP_DAILY_AI_CAP=1500
DISCOVERY=osm
```

## Redeploy

```
gcloud run deploy needproof --source . --region asia-southeast1 \
  --service-account needproof-run@project-e191c6db-1912-4df5-acf.iam.gserviceaccount.com \
  --allow-unauthenticated --min-instances 0 --max-instances 1 --memory 1Gi
```
(environment variables persist between deploys unless changed with `--update-env-vars`)

## Looker Studio dashboard

Open this link while signed in to the project owner's account, then press **Save**. It creates a report with both
BigQuery views as data sources:

https://lookerstudio.google.com/reporting/create?c.mode=edit&r.reportName=NeedProof+unmet+demand&ds.ds0.connector=bigQuery&ds.ds0.type=TABLE&ds.ds0.projectId=project-e191c6db-1912-4df5-acf&ds.ds0.datasetId=needproof_loop&ds.ds0.tableId=unmet_demand&ds.ds0.datasourceName=Unmet+demand+%2828+days%29&ds.ds1.connector=bigQuery&ds.ds1.type=TABLE&ds.ds1.projectId=project-e191c6db-1912-4df5-acf&ds.ds1.datasetId=needproof_loop&ds.ds1.tableId=daily_demand&ds.ds1.datasourceName=Daily+demand

Suggested charts: bar of `unmet` by `product` filtered by `city`; time series of `asks` by `day` from Daily demand.

## Costs at demo traffic

| Service | Expected |
|---|---|
| Cloud Run (min 0) | ₹0 within free tier (2M requests, 180k vCPU-s per month) |
| Vertex AI Gemini 2.5 Flash-Lite | a few rupees per few hundred conversations |
| BigQuery | ₹0 (well under 1 TB queried / 10 GB stored free) |
| BigQuery ML ARIMA_PLUS retrain | cents per retrain at this size |
| Vertex AI Search | small per-query charge; a few hundred queries is under ₹100 |
| Cloud Storage | ₹0 (a few MB) |
| Cloud SQL (not created yet) | about ₹25–30/day while it exists; create just before judging, delete after |

## Tear down after the event

```
gcloud run services delete needproof --region asia-southeast1
gcloud storage rm -r gs://needproof-media-822406860102
bq rm -r -f needproof_loop
# Vertex AI Search: delete engine needproof-inventory-search, then data store needproof-inventory (console)
```
