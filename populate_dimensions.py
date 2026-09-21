"""Populate the dimension tables required by the dashboard demo.

The transaction generators select merchants from ``bank_demo.merchants``. A
fresh ClickHouse database only creates that table, so this small idempotent
loader must be run before generating a baseline or starting ``producer.py``.
"""

import argparse
from itertools import islice
from typing import Iterable, Iterator, List, Sequence, Tuple

import clickhouse_connect

from generate_baseline import GATEWAY_LATENCY_PROFILE, MERCHANT_CATEGORIES


REGIONS = ["California", "Texas", "New York", "Florida", "Illinois", "Pennsylvania", "Ohio", "Georgia"]
GATEWAYS = list(GATEWAY_LATENCY_PROFILE)
SEGMENTS = ["Mass Market", "Affluent", "Small Business", "Commercial"]


def batches(rows: Iterable[Tuple], size: int) -> Iterator[List[Tuple]]:
    iterator = iter(rows)
    while batch := list(islice(iterator, size)):
        yield batch


def merchant_rows(per_category: int) -> Iterator[Tuple[int, str, str, str, int]]:
    merchant_id = 1
    for category_index, category in enumerate(MERCHANT_CATEGORIES):
        for offset in range(per_category):
            gateway = GATEWAYS[(category_index + offset) % len(GATEWAYS)]
            region = REGIONS[(category_index * 3 + offset) % len(REGIONS)]
            daily_volume = 5_000 + ((merchant_id * 7_919) % 500_000)
            yield (
                merchant_id,
                f"{category.replace(' ', '')} Merchant {merchant_id:05d}",
                category,
                gateway,
                region,
                daily_volume,
            )
            merchant_id += 1


def customer_rows(count: int) -> Iterator[Tuple[int, str, float, str]]:
    for customer_id in range(1, count + 1):
        yield (
            customer_id,
            SEGMENTS[(customer_id - 1) % len(SEGMENTS)],
            round(250 + ((customer_id * 3_571) % 250_000) / 10, 2),
            REGIONS[(customer_id - 1) % len(REGIONS)],
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate Banking Control Tower dimensions")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--database", default="bank_demo")
    parser.add_argument("--user", default="demo")
    parser.add_argument("--password", default="demo_pass")
    parser.add_argument("--merchants-per-category", type=int, default=2_500)
    parser.add_argument("--customers", type=int, default=200_000)
    parser.add_argument("--batch-size", type=int, default=10_000)
    args = parser.parse_args()

    if args.merchants_per_category < 1 or args.customers < 1 or args.batch_size < 1:
        parser.error("--merchants-per-category, --customers, and --batch-size must be positive")

    client = clickhouse_connect.get_client(
        host=args.host, port=args.port, database=args.database,
        username=args.user, password=args.password,
    )

    existing_merchants = client.command("SELECT count() FROM merchants")
    if existing_merchants:
        print(f"Merchants already populated ({existing_merchants:,} rows); leaving them unchanged.")
    else:
        for rows in batches(merchant_rows(args.merchants_per_category), args.batch_size):
            client.insert(
                "merchants", rows,
                column_names=["merchant_id", "merchant_name", "merchant_category", "gateway", "region", "avg_daily_volume"],
            )
        print(f"Inserted {args.merchants_per_category * len(MERCHANT_CATEGORIES):,} merchants.")

    existing_customers = client.command("SELECT count() FROM customers")
    if existing_customers:
        print(f"Customers already populated ({existing_customers:,} rows); leaving them unchanged.")
    else:
        for rows in batches(customer_rows(args.customers), args.batch_size):
            client.insert(
                "customers", rows,
                column_names=["customer_id", "segment", "lifetime_value", "home_region"],
            )
        print(f"Inserted {args.customers:,} customers.")


if __name__ == "__main__":
    main()
