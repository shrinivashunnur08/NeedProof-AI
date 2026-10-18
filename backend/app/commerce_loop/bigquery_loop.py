"""BigQuery side of the commerce loop (google_full profile, or ANALYTICS_BACKEND=bigquery).

- sync():      load demand events into BigQuery and retrain the BigQuery ML ARIMA_PLUS model
- forecast():  ML.FORECAST for one city (7 days, 90% interval)
- ai_brief():  AI.GENERATE: Gemini writes the shop brief inside BigQuery, from the unmet-demand view

The same SQL lives in infra/bigquery/ for anyone who wants to run it by hand.
"""
from __future__ import annotations

import time
from pathlib import Path

from app.commerce_loop import store
from app.commerce_loop.insights import export_events_ndjson
from app.commerce_loop.providers import get_providers, setting

_CACHE: dict[str, tuple[float, dict]] = {}
SCHEMA = (("city", "STRING"), ("product_key", "STRING"), ("product", "STRING"), ("budget", "FLOAT"),
          ("currency", "STRING"), ("answered", "BOOLEAN"), ("source", "STRING"), ("created_at", "TIMESTAMP"))


class BigQueryUnavailable(RuntimeError):
    pass


def _ctx():
    p = get_providers()
    if p.analytics_backend != "bigquery" or not p.gcp_project:
        raise BigQueryUnavailable("Set ANALYTICS_BACKEND=bigquery and GOOGLE_CLOUD_PROJECT to use BigQuery")
    try:
        from google.cloud import bigquery
    except ImportError as exc:
        raise BigQueryUnavailable("pip install google-cloud-bigquery") from exc
    location = setting("BIGQUERY_LOCATION", "asia-southeast1")
    client = bigquery.Client(project=p.gcp_project, location=location)
    return bigquery, client, f"{p.gcp_project}.{p.bigquery_dataset}", location


def _console(project_ds: str) -> str:
    project, dataset = project_ds.split(".", 1)
    return f"https://console.cloud.google.com/bigquery?project={project}&ws=!1m4!1m3!3m2!1s{project}!2s{dataset}"


def sync() -> dict:
    bigquery, client, ds, location = _ctx()
    started = time.perf_counter()
    tmp = Path(store.db_path()).with_suffix(".bq.ndjson")
    rows = export_events_ndjson(tmp)
    dataset = bigquery.Dataset(ds)
    dataset.location = location
    client.create_dataset(dataset, exists_ok=True)
    with open(tmp, "rb") as fh:
        client.load_table_from_file(fh, f"{ds}.demand_events", job_config=bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON, write_disposition="WRITE_TRUNCATE",
            schema=[bigquery.SchemaField(n, t) for n, t in SCHEMA])).result()
    client.query(f"""
CREATE OR REPLACE VIEW `{ds}.unmet_demand` AS
SELECT city, product_key, ANY_VALUE(product) AS product, COUNT(*) AS asks, COUNTIF(answered) AS answered,
       COUNTIF(NOT answered) AS unmet, ROUND(SAFE_DIVIDE(COUNTIF(NOT answered), COUNT(*)), 2) AS unmet_rate,
       ROUND(AVG(budget), 0) AS avg_budget, ANY_VALUE(currency) AS currency
FROM `{ds}.demand_events`
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 28 DAY)
GROUP BY city, product_key;
CREATE OR REPLACE VIEW `{ds}.daily_demand` AS
SELECT city, product_key, DATE(created_at) AS day, COUNT(*) AS asks, COUNTIF(NOT answered) AS unmet
FROM `{ds}.demand_events` GROUP BY city, product_key, day;
CREATE OR REPLACE MODEL `{ds}.demand_forecast`
OPTIONS (model_type = 'ARIMA_PLUS', time_series_timestamp_col = 'day', time_series_data_col = 'asks',
         time_series_id_col = ['city', 'product_key'], horizon = 14, auto_arima = TRUE, data_frequency = 'DAILY')
AS SELECT city, product_key, TIMESTAMP(day) AS day, asks FROM `{ds}.daily_demand`;
""").result()
    _CACHE.clear()
    return {"rows": rows, "dataset": ds, "location": location, "model": f"{ds}.demand_forecast",
            "seconds": round(time.perf_counter() - started, 1), "console_url": _console(ds)}


def forecast(city: str) -> dict:
    key = f"fc:{city}"
    if key in _CACHE and time.time() - _CACHE[key][0] < 300:
        return _CACHE[key][1]
    bigquery, client, ds, location = _ctx()
    job = client.query(
        f"""SELECT product_key, ROUND(SUM(forecast_value), 1) AS next_7_days,
                   ROUND(SUM(prediction_interval_lower_bound), 1) AS low,
                   ROUND(SUM(prediction_interval_upper_bound), 1) AS high
            FROM ML.FORECAST(MODEL `{ds}.demand_forecast`, STRUCT(7 AS horizon, 0.9 AS confidence_level))
            WHERE city = @city GROUP BY product_key ORDER BY next_7_days DESC""",
        job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("city", "STRING", city)]))
    rows = [dict(r) for r in job.result()]
    out = {"city": city, "rows": rows, "model": f"{ds}.demand_forecast", "engine": "BigQuery ML ARIMA_PLUS",
           "job_id": job.job_id, "console_url": _console(ds)}
    _CACHE[key] = (time.time(), out)
    return out


def ai_brief(city: str) -> dict:
    bigquery, client, ds, location = _ctx()
    conn = setting("BIGQUERY_CONNECTION", f"{location}.vertex_conn")
    model = setting("BIGQUERY_AI_MODEL", "gemini-2.5-flash")
    started = time.perf_counter()
    job = client.query(
        f"""SELECT AI.GENERATE(
              CONCAT('Write a three-bullet weekly brief for a small electronics shop in ', ANY_VALUE(city),
                     '. Plain text, one line per bullet starting with "- ". Use only these numbers ',
                     '(asks = shopper requests, unmet = no shop confirmed stock): ',
                     TO_JSON_STRING(ARRAY_AGG(STRUCT(product, asks, unmet, avg_budget, currency)
                                              ORDER BY unmet DESC LIMIT 4))),
              connection_id => '{conn}', endpoint => '{model}').result AS brief
            FROM `{ds}.unmet_demand` WHERE city = @city""",
        job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("city", "STRING", city)]))
    rows = list(job.result())
    text = (rows[0]["brief"] if rows else "") or ""
    bullets = [b.strip().lstrip("-*• ").strip() for b in text.splitlines() if b.strip().lstrip("-*• ").strip()]
    return {"city": city, "bullets": bullets[:5], "engine": f"BigQuery AI.GENERATE ({model})", "job_id": job.job_id,
            "seconds": round(time.perf_counter() - started, 1), "console_url": _console(ds)}
