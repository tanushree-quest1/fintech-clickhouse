-- Run this AFTER Kafka is up and the `transactions` topic exists (or let
-- Kafka auto-create it on first produce).
--
-- This creates a Kafka "queue" table (an ephemeral view over the topic) and
-- a materialized view that pushes every consumed message into the real
-- `transactions` MergeTree table.

CREATE TABLE IF NOT EXISTS bank_demo.transactions_kafka_queue
(
    transaction_id        String,
    event_time             DateTime64(3),
    customer_id            UInt64,
    account_id             UInt64,
    merchant_id            UInt64,
    device_id              UInt64,
    bank                   String,
    payment_rail           String,
    region                 String,
    merchant_category      String,
    gateway                String,
    payment_method         String,
    amount                 Decimal64(2),
    currency               String,
    authorization_status   String,
    response_code          String,
    settlement_status      String,
    fraud_score            Float32,
    latency_ms             Float32,
    is_synthetic_incident  UInt8
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'transactions',
    kafka_group_name = 'ch_consumer_group',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1,
    kafka_skip_broken_messages = 10;

CREATE MATERIALIZED VIEW IF NOT EXISTS bank_demo.mv_kafka_to_transactions
TO bank_demo.transactions
AS
SELECT
    toUUID(transaction_id) AS transaction_id,
    event_time,
    customer_id, account_id, merchant_id, device_id,
    bank, payment_rail, region, merchant_category, gateway, payment_method,
    amount, currency, authorization_status, response_code, settlement_status,
    fraud_score, latency_ms, is_synthetic_incident
FROM bank_demo.transactions_kafka_queue;