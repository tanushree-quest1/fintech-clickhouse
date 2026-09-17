"""
Historical backfill — Banking Control Tower demo.

Generates pure-baseline (no-incident) data for the past N days, at a lower
per-day density than the live-demo window, so "same time yesterday / same
time last week" comparison queries in the demo have real data to compare
against.

Reuses the same distributions as generate_baseline.py so today's live window
and history look like the same system, just shifted in time.

Usage:
    python backfill_history.py --days 90 --rows-per-day 300000
"""

import argparse
from datetime import datetime, timedelta

import numpy as np
import clickhouse_connect

from generate_baseline import generate_batch  # reuse the same row generator
from merchant_catalog import MerchantCatalog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--rows-per-day", type=int, default=300_000)
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--database", default="bank_demo")
    parser.add_argument("--user", default="demo")
    parser.add_argument("--password", default="demo_pass")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--skip-most-recent-hours", type=int, default=6,
                         help="Leave this many recent hours alone — that's the live-demo window "
                              "already populated by generate_baseline.py")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

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

    now = datetime.utcnow()
    live_window_start = now - timedelta(hours=args.skip_most_recent_hours)

    total_inserted = 0
    grand_total = args.days * args.rows_per_day

    for day_offset in range(1, args.days + 1):
        day_end = live_window_start - timedelta(days=day_offset - 1)
        day_start = day_end - timedelta(days=1)
        span_seconds = int((day_end - day_start).total_seconds())

        remaining = args.rows_per_day
        while remaining > 0:
            batch_n = min(args.batch_size, remaining)
            rows = generate_batch(batch_n, day_start, span_seconds, rng, catalog=catalog)
            client.insert("transactions", rows, column_names=columns)
            remaining -= batch_n
            total_inserted += batch_n

        print(f"Day -{day_offset}: inserted {args.rows_per_day:,} rows "
              f"({total_inserted:,}/{grand_total:,} total) "
              f"[{day_start.date()} to {day_end.date()}]")

    print("Backfill complete. Verifying date coverage...")
    result = client.query("""
        SELECT
            event_date,
            count() AS rows,
            round(100 * countIf(authorization_status = 'FAILED') / count(), 2) AS failure_rate_pct
        FROM transactions
        GROUP BY event_date
        ORDER BY event_date DESC
        LIMIT 10
    """)
    for row in result.result_rows:
        print(row)


if __name__ == "__main__":
    main()