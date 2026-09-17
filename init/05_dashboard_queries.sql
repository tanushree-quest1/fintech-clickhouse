-- ============================================================================
-- Banking Control Tower — Dashboard Query Library
-- ============================================================================
-- Organized by demo step (per rta_demo_suggestion.md). Each query is
-- self-contained and parameterizable — swap the WHERE filters as the demo
-- drills deeper.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. TOP-LEVEL KPI STRIP (uses the 1-minute aggregate, not raw transactions)
-- ----------------------------------------------------------------------------
-- Powers: "Transactions ₹1.82B | 2.41M | ▲8.7%", "Success Rate 98.21%", etc.

SELECT
    countMerge(total) AS total_txns,
    round(100 * (1 - (countIfMerge(failed) / countMerge(total))), 2) AS success_rate_pct,
    round(avgMerge(avg_latency), 1) AS avg_latency_ms
FROM transactions_1m_agg
WHERE minute >= now() - INTERVAL 15 MINUTE;

-- Volume trend vs prior 15-minute window, for the "▲8.7%" delta arrow:
WITH
    (SELECT countMerge(total) FROM transactions_1m_agg
     WHERE minute >= now() - INTERVAL 15 MINUTE) AS current_window,
    (SELECT countMerge(total) FROM transactions_1m_agg
     WHERE minute >= now() - INTERVAL 30 MINUTE AND minute < now() - INTERVAL 15 MINUTE) AS prior_window
SELECT
    current_window,
    prior_window,
    round(100 * (current_window - prior_window) / prior_window, 2) AS pct_change;


-- ----------------------------------------------------------------------------
-- 2. ANOMALY DETECTION — flags the "⚠ ANOMALY DETECTED" banner
-- ----------------------------------------------------------------------------
-- Compares current failure rate per (rail, region, category, gateway) slice
-- against a trailing 24-hour baseline for the same slice. Surfaces any slice
-- whose current failure rate deviates sharply from its own historical norm —
-- this is what would actually catch Gateway Y without hardcoding it.

WITH
    current_stats AS (
        SELECT
            payment_rail, region, merchant_category, gateway,
            count() AS total,
            countIf(authorization_status = 'FAILED') AS failed,
            failed / total AS failure_rate
        FROM transactions
        WHERE event_time >= now() - INTERVAL 5 MINUTE
        GROUP BY payment_rail, region, merchant_category, gateway
        HAVING total > 50   -- ignore statistically noisy tiny slices
    ),
    baseline_stats AS (
        SELECT
            payment_rail, region, merchant_category, gateway,
            countIf(authorization_status = 'FAILED') / count() AS baseline_failure_rate
        FROM transactions
        WHERE event_time >= now() - INTERVAL 1 DAY
          AND event_time < now() - INTERVAL 1 HOUR   -- exclude the live/incident window
        GROUP BY payment_rail, region, merchant_category, gateway
    )
SELECT
    c.payment_rail, c.region, c.merchant_category, c.gateway,
    round(100 * c.failure_rate, 2) AS current_failure_rate_pct,
    round(100 * b.baseline_failure_rate, 2) AS baseline_failure_rate_pct,
    round(c.failure_rate / b.baseline_failure_rate, 1) AS times_above_baseline
FROM current_stats c
JOIN baseline_stats b USING (payment_rail, region, merchant_category, gateway)
WHERE c.failure_rate > b.baseline_failure_rate * 2   -- flag anything 2x+ its own norm
ORDER BY times_above_baseline DESC
LIMIT 10;


-- ----------------------------------------------------------------------------
-- 3. DRILL-DOWN CHAIN — Bank → Rail → Region → Category → Gateway → Merchant
-- ----------------------------------------------------------------------------
-- Run each level in sequence during the demo, narrowing the WHERE clause as
-- you go. Each step is the same query shape, just adding a filter.

-- 3a. Bank level
SELECT bank, count() AS total, countIf(authorization_status = 'FAILED') AS failed,
       round(100 * failed / total, 2) AS failure_rate_pct
FROM transactions WHERE event_time >= now() - INTERVAL 15 MINUTE
GROUP BY bank ORDER BY failure_rate_pct DESC;

-- 3b. + Rail
SELECT payment_rail, count() AS total, countIf(authorization_status = 'FAILED') AS failed,
       round(100 * failed / total, 2) AS failure_rate_pct
FROM transactions WHERE event_time >= now() - INTERVAL 15 MINUTE
GROUP BY payment_rail ORDER BY failure_rate_pct DESC;

-- 3c. + Region (within UPI)
SELECT region, count() AS total, countIf(authorization_status = 'FAILED') AS failed,
       round(100 * failed / total, 2) AS failure_rate_pct
FROM transactions
WHERE event_time >= now() - INTERVAL 15 MINUTE AND payment_rail = 'UPI'
GROUP BY region ORDER BY failure_rate_pct DESC;

-- 3d. + Merchant category (within UPI/Mumbai)
SELECT merchant_category, count() AS total, countIf(authorization_status = 'FAILED') AS failed,
       round(100 * failed / total, 2) AS failure_rate_pct
FROM transactions
WHERE event_time >= now() - INTERVAL 15 MINUTE AND payment_rail = 'UPI' AND region = 'Mumbai'
GROUP BY merchant_category ORDER BY failure_rate_pct DESC;

-- 3e. + Gateway (within UPI/Mumbai/E-commerce)
SELECT gateway, count() AS total, countIf(authorization_status = 'FAILED') AS failed,
       round(100 * failed / total, 2) AS failure_rate_pct,
       round(avg(latency_ms), 1) AS avg_latency_ms
FROM transactions
WHERE event_time >= now() - INTERVAL 15 MINUTE
  AND payment_rail = 'UPI' AND region = 'Mumbai' AND merchant_category = 'E-commerce'
GROUP BY gateway ORDER BY failure_rate_pct DESC;

-- 3f. + Merchant (within the full incident slice, top offenders)
SELECT m.merchant_name, count() AS total,
       countIf(t.authorization_status = 'FAILED') AS failed,
       round(100 * failed / total, 2) AS failure_rate_pct
FROM transactions t
JOIN merchants m USING (merchant_id)
WHERE t.event_time >= now() - INTERVAL 15 MINUTE
  AND t.payment_rail = 'UPI' AND t.region = 'Mumbai'
  AND t.merchant_category = 'E-commerce' AND t.gateway = 'Gateway Y'
GROUP BY m.merchant_name ORDER BY failed DESC LIMIT 20;


-- ----------------------------------------------------------------------------
-- 4. ROOT CAUSE — the response-code / gateway breakdown from the brief
-- ----------------------------------------------------------------------------

SELECT
    gateway,
    response_code,
    count() AS failures,
    round(avg(latency_ms), 1) AS latency_ms
FROM transactions
WHERE event_time >= now() - INTERVAL 10 MINUTE
  AND authorization_status = 'FAILED'
GROUP BY gateway, response_code
ORDER BY failures DESC
LIMIT 20;


-- ----------------------------------------------------------------------------
-- 5. HISTORICAL COMPARISON — "is this actually anomalous?"
-- ----------------------------------------------------------------------------

WITH
    today_stats AS (
        SELECT
            countIf(authorization_status = 'FAILED') AS failures,
            count() AS total,
            round(100 * (1 - failures / total), 2) AS success_pct,
            round(avg(latency_ms), 1) AS avg_latency
        FROM transactions
        WHERE payment_rail = 'UPI' AND region = 'Mumbai' AND gateway = 'Gateway Y'
          AND event_time >= now() - INTERVAL 15 MINUTE
    ),
    yesterday_stats AS (
        SELECT
            countIf(authorization_status = 'FAILED') AS failures,
            count() AS total,
            round(100 * (1 - failures / total), 2) AS success_pct,
            round(avg(latency_ms), 1) AS avg_latency
        FROM transactions
        WHERE payment_rail = 'UPI' AND region = 'Mumbai' AND gateway = 'Gateway Y'
          AND event_time >= now() - INTERVAL 1 DAY - INTERVAL 15 MINUTE
          AND event_time < now() - INTERVAL 1 DAY
    ),
    last_week_stats AS (
        SELECT
            countIf(authorization_status = 'FAILED') AS failures,
            count() AS total,
            round(100 * (1 - failures / total), 2) AS success_pct,
            round(avg(latency_ms), 1) AS avg_latency
        FROM transactions
        WHERE payment_rail = 'UPI' AND region = 'Mumbai' AND gateway = 'Gateway Y'
          AND event_time >= now() - INTERVAL 7 DAY - INTERVAL 15 MINUTE
          AND event_time < now() - INTERVAL 7 DAY
    )
SELECT
    'Today (live)' AS period, * FROM today_stats
UNION ALL
SELECT 'Same time yesterday', * FROM yesterday_stats
UNION ALL
SELECT 'Same time last week', * FROM last_week_stats;


-- ----------------------------------------------------------------------------
-- 6. BUSINESS IMPACT — customers and merchants affected
-- ----------------------------------------------------------------------------

-- 6a. Affected customers, segmented
SELECT
    c.segment,
    count(DISTINCT t.customer_id) AS affected_customers,
    round(sum(t.amount), 2) AS value_at_risk
FROM transactions t
JOIN customers c USING (customer_id)
WHERE t.event_time >= now() - INTERVAL 15 MINUTE
  AND t.authorization_status = 'FAILED'
  AND t.payment_rail = 'UPI' AND t.region = 'Mumbai'
  AND t.merchant_category = 'E-commerce' AND t.gateway = 'Gateway Y'
GROUP BY c.segment
ORDER BY value_at_risk DESC;

-- 6b. Most affected merchants
SELECT
    m.merchant_name,
    count() AS failed_txns,
    round(sum(t.amount), 2) AS value_at_risk
FROM transactions t
JOIN merchants m USING (merchant_id)
WHERE t.event_time >= now() - INTERVAL 15 MINUTE
  AND t.authorization_status = 'FAILED'
  AND t.payment_rail = 'UPI' AND t.region = 'Mumbai'
  AND t.merchant_category = 'E-commerce' AND t.gateway = 'Gateway Y'
GROUP BY m.merchant_name
ORDER BY value_at_risk DESC
LIMIT 15;