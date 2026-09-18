"""
Baseline synthetic data generator — Banking Control Tower demo.

Generates realistic (non-incident) transaction data and bulk-inserts it into
ClickHouse via clickhouse-connect. Run this first to validate distributions
before moving to historical backfill or live streaming.

Usage:
    pip install clickhouse-connect numpy
    python generate_baseline.py --rows 5000000 --batch-size 100000
"""

import argparse
import random
import uuid
from datetime import datetime, timedelta

import numpy as np
import clickhouse_connect

from merchant_catalog import MerchantCatalog

# ---------------------------------------------------------------------------
# Dimension pools — weighted to look like a real US payments mix
# ---------------------------------------------------------------------------

BANKS = ["Chase", "Bank of America", "Wells Fargo", "Citibank", "US Bank"]
BANK_WEIGHTS = [0.28, 0.24, 0.22, 0.14, 0.12]

RAILS = ["Card", "ACH", "Wire", "Zelle", "PayPal"]
RAIL_WEIGHTS = [0.45, 0.25, 0.10, 0.12, 0.08]

REGIONS = ["California", "Texas", "New York", "Florida", "Illinois", "Pennsylvania", "Ohio", "Georgia"]
REGION_WEIGHTS = [0.22, 0.18, 0.16, 0.10, 0.10, 0.09, 0.08, 0.07]

MERCHANT_CATEGORIES = ["E-commerce", "Travel", "Food Delivery", "Utilities", "Groceries", "Entertainment"]
CATEGORY_WEIGHTS = [0.32, 0.12, 0.20, 0.14, 0.14, 0.08]

GATEWAYS = ["Gateway A", "Gateway B", "Gateway X", "Gateway Y", "Gateway Z"]
GATEWAY_WEIGHTS = [0.24, 0.24, 0.18, 0.18, 0.16]

# Per-gateway latency profile: (mean_ms, stddev_ms) — gives each gateway a
# distinct fingerprint so root-cause-by-gateway queries look meaningful
GATEWAY_LATENCY_PROFILE = {
    "Gateway A": (180, 40),
    "Gateway B": (220, 55),
    "Gateway X": (260, 70),
    "Gateway Y": (300, 90),   # slightly heavier baseline — this is our incident target
    "Gateway Z": (200, 50),
}

PAYMENT_METHODS_BY_RAIL = {
    "Card": ["Debit Card", "Credit Card"],
    "ACH": ["ACH-Debit", "ACH-Credit"],
    "Wire": ["Wire-Domestic", "Wire-International"],
    "Zelle": ["Zelle-Personal", "Zelle-Business"],
    "PayPal": ["PayPal-Standard", "PayPal-Business"],
}

CURRENCY = "USD"

FAILURE_RESPONSE_CODES = ["91", "96", "51", "05", "U30"]
FAILURE_CODE_WEIGHTS = [0.35, 0.20, 0.20, 0.15, 0.10]

BASELINE_SUCCESS_RATE = 0.981  # ~98.1%, matches the brief's stated baseline

# Amount distribution parameters per category: (lognormal mean, sigma) in USD
AMOUNT_PARAMS = {
    "E-commerce": (4.5, 0.9),
    "Travel": (6.0, 1.1),
    "Food Delivery": (3.2, 0.5),
    "Utilities": (4.0, 0.6),
    "Groceries": (3.5, 0.6),
    "Entertainment": (3.8, 0.7),
}


def generate_batch(n: int, start_time: datetime, span_seconds: int, rng: np.random.Generator,
                    catalog=None):
    """
    Generate n baseline (non-incident) rows spread across span_seconds.

    catalog: a MerchantCatalog (see merchant_catalog.py). Required — merchant_id,
    merchant_category, gateway, and region are ALL derived from the sampled
    merchant, never independently re-rolled, so a merchant's category/gateway/
    region are internally consistent across every transaction it appears in.
    Popularity is Zipf-skewed within category so a few merchants dominate volume.
    """
    if catalog is None:
        raise ValueError("generate_batch requires a MerchantCatalog — see merchant_catalog.py")

    rows = []

    banks = rng.choice(BANKS, size=n, p=BANK_WEIGHTS)
    rails = rng.choice(RAILS, size=n, p=RAIL_WEIGHTS)
    categories = rng.choice(MERCHANT_CATEGORIES, size=n, p=CATEGORY_WEIGHTS)

    raw_offsets = rng.integers(0, span_seconds, size=n)
    timestamps = [start_time + timedelta(seconds=int(o)) for o in raw_offsets]

    success_roll = rng.random(n)
    fraud_scores = rng.beta(2, 20, size=n)

    # Sample merchants per-category in bulk where possible (group by category
    # to batch the catalog sampling call instead of one-by-one)
    merchant_ids = np.empty(n, dtype=np.int64)
    merchant_gateways = np.empty(n, dtype=object)
    merchant_regions = np.empty(n, dtype=object)
    for cat in MERCHANT_CATEGORIES:
        mask = categories == cat
        cnt = int(mask.sum())
        if cnt == 0:
            continue
        ids, gws, regs = catalog.sample(cat, rng, size=cnt)
        merchant_ids[mask] = ids
        merchant_gateways[mask] = gws
        merchant_regions[mask] = regs

    for i in range(n):
        rail = rails[i]
        cat = categories[i]
        gw = merchant_gateways[i]
        region = merchant_regions[i]
        mean_lat, std_lat = GATEWAY_LATENCY_PROFILE[gw]

        is_success = success_roll[i] < BASELINE_SUCCESS_RATE
        status = "SUCCESS" if is_success else "FAILED"
        resp_code = "00" if is_success else rng.choice(FAILURE_RESPONSE_CODES, p=FAILURE_CODE_WEIGHTS)

        lat_mean = mean_lat if is_success else mean_lat * 2.4
        latency = max(5.0, rng.normal(lat_mean, std_lat))

        mean_amt, sigma_amt = AMOUNT_PARAMS[cat]
        amount = round(float(rng.lognormal(mean_amt, sigma_amt)), 2)
        amount = min(amount, 500000.00)

        method = random.choice(PAYMENT_METHODS_BY_RAIL[rail])

        rows.append((
            str(uuid.uuid4()),
            timestamps[i],
            int(rng.integers(1, 2_000_000)),
            int(rng.integers(1, 2_500_000)),
            int(merchant_ids[i]),
            int(rng.integers(1, 5_000_000)),
            banks[i],
            rail,
            region,
            cat,
            gw,
            method,
            amount,
            CURRENCY,
            status,
            resp_code,
            "SETTLED" if is_success else "NOT_SETTLED",
            round(float(fraud_scores[i]), 4),
            round(float(latency), 2),
            0,
        ))

    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=5_000_000)
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--database", default="bank_demo")
    parser.add_argument("--user", default="demo")
    parser.add_argument("--password", default="demo_pass")
    parser.add_argument("--hours-back", type=int, default=6,
                         help="Spread generated rows over the last N hours ending now")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    random.seed(args.seed)

    client = clickhouse_connect.get_client(
        host=args.host, port=args.port, database=args.database,
        username=args.user, password=args.password,
    )

    print("Loading merchant catalog...")
    catalog = MerchantCatalog(client)

    columns = [
        "transaction_id", "event_time", "customer_id", "account_id",
        "merchant_id", "device_id", "bank", "payment_rail", "region",
        "merchant_category", "gateway", "payment_method", "amount",
        "currency", "authorization_status", "response_code",
        "settlement_status", "fraud_score", "latency_ms",
        "is_synthetic_incident",
    ]

    span_seconds = args.hours_back * 3600
    start_time = datetime.utcnow() - timedelta(seconds=span_seconds)

    total_inserted = 0
    n_batches = (args.rows + args.batch_size - 1) // args.batch_size

    for b in range(n_batches):
        batch_n = min(args.batch_size, args.rows - total_inserted)
        rows = generate_batch(batch_n, start_time, span_seconds, rng, catalog=catalog)
        client.insert("transactions", rows, column_names=columns)
        total_inserted += batch_n
        print(f"[{b + 1}/{n_batches}] inserted {total_inserted:,}/{args.rows:,} rows")

    print("Done. Running quick sanity check...")
    result = client.query("""
        SELECT
            bank, payment_rail, gateway,
            count() AS total,
            countIf(authorization_status = 'FAILED') AS failed,
            round(100 * failed / total, 2) AS failure_rate_pct,
            round(avg(latency_ms), 1) AS avg_latency_ms
        FROM transactions
        GROUP BY bank, payment_rail, gateway
        ORDER BY total DESC
        LIMIT 10
    """)
    for row in result.result_rows:
        print(row)


if __name__ == "__main__":
    main()