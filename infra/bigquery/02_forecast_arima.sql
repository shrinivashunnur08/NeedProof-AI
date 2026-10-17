-- BigQuery ML demand forecast per city and product (google_full profile).
-- The local app uses a simple week-over-week estimate; this replaces it at scale.
CREATE OR REPLACE MODEL needproof_loop.demand_forecast
OPTIONS (
  model_type = 'ARIMA_PLUS',
  time_series_timestamp_col = 'day',
  time_series_data_col = 'asks',
  time_series_id_col = ['city', 'product_key'],
  horizon = 14,
  auto_arima = TRUE,
  data_frequency = 'DAILY'
) AS
SELECT city, product_key, TIMESTAMP(day) AS day, asks
FROM needproof_loop.daily_demand;

-- Next 7 days with a 90% interval.
SELECT city, product_key, forecast_timestamp, ROUND(forecast_value, 1) AS expected_asks,
       ROUND(prediction_interval_lower_bound, 1) AS low, ROUND(prediction_interval_upper_bound, 1) AS high
FROM ML.FORECAST(MODEL needproof_loop.demand_forecast, STRUCT(7 AS horizon, 0.9 AS confidence_level))
ORDER BY city, product_key, forecast_timestamp;
