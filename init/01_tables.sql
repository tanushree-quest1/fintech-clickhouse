CREATE TABLE IF NOT EXISTS bank_demo.transactions
(
    transaction_id        UUID,
    event_time             DateTime64(3),
    event_date             Date DEFAULT toDate(event_time),

    customer_id            UInt64,
    account_id             UInt64,
    merchant_id            UInt64,
    device_id              UInt64,

    bank                   LowCardinality(String),
    payment_rail           LowCardinality(String),
    region                 LowCardinality(String),
    merchant_category      LowCardinality(String),
    gateway                LowCardinality(String),
    payment_method         LowCardinality(String),

    amount                 Decimal64(2),
    currency               LowCardinality(String),
    authorization_status   LowCardinality(String),
    response_code          LowCardinality(String),
    settlement_status      LowCardinality(String),
    fraud_score            Float32,
    latency_ms             Float32,

    is_synthetic_incident  UInt8 DEFAULT 0
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(event_date)
ORDER BY (bank, payment_rail, region, gateway, event_time)
TTL event_date + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 8192;

ALTER TABLE bank_demo.transactions
    ADD INDEX IF NOT EXISTS idx_merchant merchant_id TYPE bloom_filter GRANULARITY 4;

ALTER TABLE bank_demo.transactions
    ADD INDEX IF NOT EXISTS idx_respcode response_code TYPE set(20) GRANULARITY 4;