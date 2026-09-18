CREATE TABLE IF NOT EXISTS bank_demo.transactions_1m_agg
(
    minute        DateTime,
    bank          LowCardinality(String),
    payment_rail  LowCardinality(String),
    region        LowCardinality(String),
    gateway       LowCardinality(String),
    total         AggregateFunction(count),
    failed        AggregateFunction(countIf, UInt8),
    avg_latency   AggregateFunction(avg, Float32),
    volume        AggregateFunction(sum, Decimal64(2))
)
ENGINE = AggregatingMergeTree
ORDER BY (bank, payment_rail, region, gateway, minute);

CREATE MATERIALIZED VIEW IF NOT EXISTS bank_demo.mv_transactions_1m
TO bank_demo.transactions_1m_agg
AS
SELECT
    toStartOfMinute(event_time) AS minute,
    bank, payment_rail, region, gateway,
    countState()                                   AS total,
    countIfState(authorization_status = 'FAILED')  AS failed,
    avgState(latency_ms)                           AS avg_latency,
    sumState(amount)                               AS volume
FROM bank_demo.transactions
GROUP BY minute, bank, payment_rail, region, gateway;