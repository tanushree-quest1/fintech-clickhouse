-- Fast paths for the dashboard's repeated response-code and anomaly queries.
-- Run once against an existing database after deploying this file. On a fresh
-- database, the INSERT is empty and the materialized view handles new events.

ALTER TABLE bank_demo.transactions
    ADD PROJECTION IF NOT EXISTS transactions_by_event_time
(
    SELECT
        transaction_id, event_time, bank, payment_rail, region, merchant_category,
        gateway, merchant_id, customer_id, amount, authorization_status,
        response_code, settlement_status, latency_ms, is_synthetic_incident
    ORDER BY (event_time, payment_rail, region, merchant_category, gateway, bank)
);

ALTER TABLE bank_demo.transactions
    MATERIALIZE PROJECTION transactions_by_event_time;

ALTER TABLE bank_demo.transactions
    ADD PROJECTION IF NOT EXISTS transactions_by_slice
(
    SELECT
        event_time, bank, payment_rail, region, merchant_category, gateway,
        merchant_id, amount, authorization_status, latency_ms
    ORDER BY (payment_rail, region, gateway, merchant_category, event_time, bank)
);

ALTER TABLE bank_demo.transactions
    MATERIALIZE PROJECTION transactions_by_slice;

CREATE TABLE IF NOT EXISTS bank_demo.transactions_slice_1m_agg
(
    minute             DateTime,
    bank               LowCardinality(String),
    payment_rail       LowCardinality(String),
    region             LowCardinality(String),
    merchant_category  LowCardinality(String),
    gateway            LowCardinality(String),
    response_code      LowCardinality(String),
    total              AggregateFunction(count),
    failed             AggregateFunction(countIf, UInt8),
    avg_latency        AggregateFunction(avg, Float32),
    volume             AggregateFunction(sum, Decimal64(2))
)
ENGINE = AggregatingMergeTree
ORDER BY (minute, payment_rail, region, merchant_category, gateway, response_code, bank);

-- Backfill existing raw history once. Do not rerun this statement after the
-- table has been populated or aggregate states will be duplicated.
INSERT INTO bank_demo.transactions_slice_1m_agg
SELECT
    toStartOfMinute(event_time) AS minute,
    bank,
    payment_rail,
    region,
    merchant_category,
    gateway,
    response_code,
    countState() AS total,
    countIfState(authorization_status = 'FAILED') AS failed,
    avgState(latency_ms) AS avg_latency,
    sumState(amount) AS volume
FROM bank_demo.transactions
GROUP BY minute, bank, payment_rail, region, merchant_category, gateway, response_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS bank_demo.mv_transactions_slice_1m
TO bank_demo.transactions_slice_1m_agg
AS
SELECT
    toStartOfMinute(event_time) AS minute,
    bank,
    payment_rail,
    region,
    merchant_category,
    gateway,
    response_code,
    countState() AS total,
    countIfState(authorization_status = 'FAILED') AS failed,
    avgState(latency_ms) AS avg_latency,
    sumState(amount) AS volume
FROM bank_demo.transactions
GROUP BY minute, bank, payment_rail, region, merchant_category, gateway, response_code;

CREATE TABLE IF NOT EXISTS bank_demo.transactions_merchant_1m_agg
(
    minute             DateTime,
    bank               LowCardinality(String),
    payment_rail       LowCardinality(String),
    region             LowCardinality(String),
    merchant_category  LowCardinality(String),
    gateway            LowCardinality(String),
    merchant_id        UInt64,
    total              AggregateFunction(count),
    failed             AggregateFunction(countIf, UInt8),
    volume             AggregateFunction(sum, Decimal64(2))
)
ENGINE = AggregatingMergeTree
ORDER BY (minute, payment_rail, region, merchant_category, gateway, bank, merchant_id);

INSERT INTO bank_demo.transactions_merchant_1m_agg
SELECT
    toStartOfMinute(event_time) AS minute,
    bank,
    payment_rail,
    region,
    merchant_category,
    gateway,
    merchant_id,
    countState() AS total,
    countIfState(authorization_status = 'FAILED') AS failed,
    sumState(amount) AS volume
FROM bank_demo.transactions
GROUP BY minute, bank, payment_rail, region, merchant_category, gateway, merchant_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS bank_demo.mv_transactions_merchant_1m
TO bank_demo.transactions_merchant_1m_agg
AS
SELECT
    toStartOfMinute(event_time) AS minute,
    bank,
    payment_rail,
    region,
    merchant_category,
    gateway,
    merchant_id,
    countState() AS total,
    countIfState(authorization_status = 'FAILED') AS failed,
    sumState(amount) AS volume
FROM bank_demo.transactions
GROUP BY minute, bank, payment_rail, region, merchant_category, gateway, merchant_id;
