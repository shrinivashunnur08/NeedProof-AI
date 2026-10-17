-- BigQuery AI: Gemini writes a shop brief directly from the unmet-demand view (google_full profile).
-- Needs a Vertex AI connection, e.g.:
--   bq mk --connection --location=US --connection_type=CLOUD_RESOURCE vertex_conn
-- and the connection's service account granted "Vertex AI User".
-- The free profile does the same thing in the backend (/api/v2/loop/cities/{city}/brief).
SELECT
  city,
  AI.GENERATE(
    CONCAT(
      'Write a three-bullet weekly brief for a small electronics shop in ', city,
      '. Use only these numbers (asks = shopper requests, unmet = no shop confirmed stock): ',
      TO_JSON_STRING(ARRAY_AGG(STRUCT(product, asks, unmet, avg_budget, currency) ORDER BY unmet DESC LIMIT 4))
    ),
    connection_id => 'us.vertex_conn',
    endpoint => 'gemini-2.5-flash'
  ).result AS brief
FROM needproof_loop.unmet_demand
GROUP BY city;
