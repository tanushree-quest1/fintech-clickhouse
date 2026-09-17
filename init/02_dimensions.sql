CREATE TABLE IF NOT EXISTS bank_demo.customers
(
    customer_id      UInt64,
    segment          LowCardinality(String),
    lifetime_value   Decimal64(2),
    home_region      LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY customer_id;

CREATE TABLE IF NOT EXISTS bank_demo.merchants
(
    merchant_id        UInt64,
    merchant_name      String,
    merchant_category  LowCardinality(String),
    gateway            LowCardinality(String),
    region             LowCardinality(String),
    avg_daily_volume   UInt32
)
ENGINE = MergeTree
ORDER BY merchant_id;