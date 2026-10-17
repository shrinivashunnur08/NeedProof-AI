-- Demand events table. Load with:
--   POST /api/v2/loop/analytics/export   (writes demand_events.ndjson)
--   bq load --source_format=NEWLINE_DELIMITED_JSON --autodetect needproof_loop.demand_events demand_events.ndjson
-- Works on the free BigQuery sandbox (batch load, no streaming).
CREATE SCHEMA IF NOT EXISTS needproof_loop;

CREATE TABLE IF NOT EXISTS needproof_loop.demand_events (
  city STRING,
  product_key STRING,
  product STRING,
  budget FLOAT64,
  currency STRING,
  answered BOOL,
  source STRING,            -- synthetic_seed | live_app
  created_at TIMESTAMP
);

-- Unmet demand by city and product (the Looker Studio dashboard reads this view).
CREATE OR REPLACE VIEW needproof_loop.unmet_demand AS
SELECT
  city,
  product_key,
  ANY_VALUE(product) AS product,
  COUNT(*) AS asks,
  COUNTIF(answered) AS answered,
  COUNTIF(NOT answered) AS unmet,
  ROUND(SAFE_DIVIDE(COUNTIF(NOT answered), COUNT(*)), 2) AS unmet_rate,
  ROUND(AVG(budget), 0) AS avg_budget,
  ANY_VALUE(currency) AS currency
FROM needproof_loop.demand_events
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 28 DAY)
GROUP BY city, product_key;

CREATE OR REPLACE VIEW needproof_loop.daily_demand AS
SELECT city, product_key, DATE(created_at) AS day, COUNT(*) AS asks, COUNTIF(NOT answered) AS unmet
FROM needproof_loop.demand_events
GROUP BY city, product_key, day;
