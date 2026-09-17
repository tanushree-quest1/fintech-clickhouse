"""
Dimension table population — Banking Control Tower demo.

Fills `customers` and `merchants` with IDs matching the ranges used in
generate_baseline.py / producer.py (customer_id 1..2_000_000, merchant_id
1..200_000), so joins in dashboard_queries.sql actually resolve.

Note: transaction generators sample IDs randomly across the full range, so
not every customer/merchant will have transactions, and vice versa the
dimension tables need full coverage of the range to avoid join misses.

Usage:
    python populate_dimensions.py
"""

import argparse

import numpy as np
import clickhouse_connect

from generate_baseline import REGIONS, REGION_WEIGHTS, MERCHANT_CATEGORIES, CATEGORY_WEIGHTS, GATEWAYS, GATEWAY_WEIGHTS, BANKS, BANK_WEIGHTS

CUSTOMER_SEGMENTS = ["Retail", "Premium", "VIP"]
SEGMENT_WEIGHTS = [0.88, 0.09, 0.03]  # VIP is intentionally rare, matches the brief's "214 VIP customers" flavor

MERCHANT_NAME_PREFIXES = [
    "American", "National", "United", "Global", "Prime", "Metro", "Central", "Pacific",
    "Coastal", "North", "South", "East", "West", "Sunrise", "Star",
]
MERCHANT_NAME_SUFFIXES = {
    "E-commerce": ["Mart", "Market", "Store", "Shop", "Retail"],
    "Travel": ["Travel", "Airlines", "Cruises", "Tours"],
    "Food Delivery": ["Eats", "Kitchen", "Foods", "Bites"],
    "Utilities": ["Utilities", "Services", "Power", "Billers"],
    "Groceries": ["Grocers", "Fresh", "Market", "Supplies"],
    "Entertainment": ["Entertainment", "Media", "Studios", "Events"],
}


def populate_customers(client, n: int, batch_size: int, rng: np.random.Generator):
    columns = ["customer_id", "segment", "lifetime_value", "home_region"]
    inserted = 0
    while inserted < n:
        batch_n = min(batch_size, n - inserted)
        ids = np.arange(inserted + 1, inserted + batch_n + 1)
        segments = rng.choice(CUSTOMER_SEGMENTS, size=batch_n, p=SEGMENT_WEIGHTS)
        regions = rng.choice(REGIONS, size=batch_n, p=REGION_WEIGHTS)

        rows = []
        for i in range(batch_n):
            seg = segments[i]
            # LTV shaped by segment so VIP/HNI actually mean something downstream
            if seg == "VIP":
                ltv = round(float(rng.lognormal(13.5, 0.6)), 2)
            elif seg == "HNI":
                ltv = round(float(rng.lognormal(11.5, 0.7)), 2)
            else:
                ltv = round(float(rng.lognormal(9.0, 0.8)), 2)
            rows.append((int(ids[i]), str(seg), min(ltv, 50_000_000.0), str(regions[i])))

        client.insert("customers", rows, column_names=columns)
        inserted += batch_n
        print(f"customers: {inserted:,}/{n:,}")


def populate_merchants(client, n: int, batch_size: int, rng: np.random.Generator):
    columns = ["merchant_id", "merchant_name", "merchant_category", "gateway", "region", "avg_daily_volume"]
    inserted = 0
    while inserted < n:
        batch_n = min(batch_size, n - inserted)
        ids = np.arange(inserted + 1, inserted + batch_n + 1)
        categories = rng.choice(MERCHANT_CATEGORIES, size=batch_n, p=CATEGORY_WEIGHTS)
        gateways = rng.choice(GATEWAYS, size=batch_n, p=GATEWAY_WEIGHTS)
        regions = rng.choice(REGIONS, size=batch_n, p=REGION_WEIGHTS)

        rows = []
        for i in range(batch_n):
            cat = categories[i]
            prefix = rng.choice(MERCHANT_NAME_PREFIXES)
            suffix = rng.choice(MERCHANT_NAME_SUFFIXES[cat])
            name = f"{prefix} {suffix} #{ids[i]}"
            avg_vol = int(max(10, rng.lognormal(6.0, 1.2)))
            rows.append((int(ids[i]), name, str(cat), str(gateways[i]), str(regions[i]), avg_vol))

        client.insert("merchants", rows, column_names=columns)
        inserted += batch_n
        print(f"merchants: {inserted:,}/{n:,}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--customers", type=int, default=2_000_000,
                         help="Must match the customer_id upper bound used in the generators")
    parser.add_argument("--merchants", type=int, default=200_000,
                         help="Must match the merchant_id upper bound used in the generators")
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--database", default="bank_demo")
    parser.add_argument("--user", default="demo")
    parser.add_argument("--password", default="demo_pass")
    parser.add_argument("--seed", type=int, default=99)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    client = clickhouse_connect.get_client(
        host=args.host, port=args.port, database=args.database,
        username=args.user, password=args.password,
    )

    populate_customers(client, args.customers, args.batch_size, rng)
    populate_merchants(client, args.merchants, args.batch_size, rng)

    print("Done. Sanity check:")
    print(client.query("SELECT segment, count() FROM customers GROUP BY segment ORDER BY count() DESC").result_rows)
    print(client.query("SELECT merchant_category, count() FROM merchants GROUP BY merchant_category ORDER BY count() DESC").result_rows)


if __name__ == "__main__":
    main()