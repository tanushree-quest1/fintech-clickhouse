"""
Live transaction producer — Banking Control Tower demo.

Streams synthetic transaction events to Kafka in real time, at a target
rate. Reuses the same distributions as generate_baseline.py so live data
and history look like one system.

Includes a small FastAPI control surface to start/stop/ramp the fault
injector during the live demo:

    POST /incident/start   -> begins ramping the incident in over ~5 min
    POST /incident/stop    -> clears the incident, returns to baseline
    GET  /incident/status  -> current injector state

Usage:
    pip install kafka-python fastapi uvicorn numpy
    python producer.py --rate 2000
    # in another terminal, during the demo:
    curl -X POST http://localhost:8000/incident/start
"""

import argparse
import json
import threading
import time
import uuid
from datetime import datetime

import numpy as np
from kafka import KafkaProducer
from fastapi import FastAPI
import uvicorn

import clickhouse_connect

from generate_baseline import (
    BANKS, BANK_WEIGHTS, RAILS, RAIL_WEIGHTS,
    MERCHANT_CATEGORIES, CATEGORY_WEIGHTS,
    GATEWAY_LATENCY_PROFILE, PAYMENT_METHODS_BY_RAIL, CURRENCY,
    FAILURE_RESPONSE_CODES, FAILURE_CODE_WEIGHTS, BASELINE_SUCCESS_RATE,
    AMOUNT_PARAMS,
)
from merchant_catalog import MerchantCatalog

RNG = np.random.default_rng()

# Loaded once at startup in main() — module-level so make_event() can use it
# without threading it through every call.
CATALOG = None


# ---------------------------------------------------------------------------
# Fault injector — runtime-controllable via the API below
# ---------------------------------------------------------------------------

class FaultInjector:
    """
    Targets: Card / California / E-commerce / Gateway Y, per the demo brief.
    Ramps failure rate + latency in over `ramp_seconds` rather than
    stepping instantly, so the dashboard visibly climbs on screen.
    """

    def __init__(self, ramp_seconds: int = 300):
        self.active = False
        self.ramp_seconds = ramp_seconds
        self.started_at = None
        self.rail = "Card"
        self.region = "California"
        self.category = "E-commerce"
        self.gateway = "Gateway Y"
        self.target_failure_rate = 0.118
        self.baseline_failure_rate = 0.019
        self.target_latency_ms = 4800
        self.lock = threading.Lock()

    def start(self):
        with self.lock:
            self.active = True
            self.started_at = time.time()

    def stop(self):
        with self.lock:
            self.active = False
            self.started_at = None

    def _ramp_fraction(self) -> float:
        if not self.active or self.started_at is None:
            return 0.0
        elapsed = time.time() - self.started_at
        return min(1.0, elapsed / self.ramp_seconds)

    def current_failure_rate(self) -> float:
        f = self._ramp_fraction()
        return self.baseline_failure_rate + f * (self.target_failure_rate - self.baseline_failure_rate)

    def current_latency_target(self, baseline_mean: float) -> float:
        f = self._ramp_fraction()
        return baseline_mean + f * (self.target_latency_ms - baseline_mean)

    def matches(self, rail, region, category, gateway) -> bool:
        return (self.active
                and rail == self.rail
                and region == self.region
                and category == self.category
                and gateway == self.gateway)

    def status(self):
        return {
            "active": self.active,
            "ramp_fraction": round(self._ramp_fraction(), 3),
            "current_failure_rate": round(self.current_failure_rate(), 4),
            "target": {
                "rail": self.rail, "region": self.region,
                "category": self.category, "gateway": self.gateway,
            },
        }


injector = FaultInjector()


# ---------------------------------------------------------------------------
# Event generation (single-row, live version of generate_batch)
# ---------------------------------------------------------------------------

def make_event() -> dict:
    bank = RNG.choice(BANKS, p=BANK_WEIGHTS)
    rail = RNG.choice(RAILS, p=RAIL_WEIGHTS)
    category = RNG.choice(MERCHANT_CATEGORIES, p=CATEGORY_WEIGHTS)

    # merchant_id, gateway, and region are ALL derived from the sampled
    # merchant (Zipf-skewed by popularity within category) — never
    # independently re-rolled, so a merchant's category/gateway/region stay
    # internally consistent, matching generate_baseline.py's logic.
    merchant_id, gateway, region = CATALOG.sample(category, RNG)
    method = RNG.choice(PAYMENT_METHODS_BY_RAIL[rail])

    mean_lat, std_lat = GATEWAY_LATENCY_PROFILE[gateway]
    is_incident_target = injector.matches(rail, region, category, gateway)

    if is_incident_target:
        fail_rate = injector.current_failure_rate()
        lat_target = injector.current_latency_target(mean_lat)
    else:
        fail_rate = 1 - BASELINE_SUCCESS_RATE
        lat_target = mean_lat

    is_success = RNG.random() > fail_rate
    status = "SUCCESS" if is_success else "FAILED"
    resp_code = "00" if is_success else str(RNG.choice(FAILURE_RESPONSE_CODES, p=FAILURE_CODE_WEIGHTS))

    lat_mean = lat_target if is_success else lat_target * 1.3
    latency = max(5.0, float(RNG.normal(lat_mean, std_lat)))

    mean_amt, sigma_amt = AMOUNT_PARAMS[category]
    amount = min(round(float(RNG.lognormal(mean_amt, sigma_amt)), 2), 500000.00)

    return {
        "transaction_id": str(uuid.uuid4()),
        "event_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "customer_id": int(RNG.integers(1, 2_000_000)),
        "account_id": int(RNG.integers(1, 2_500_000)),
        "merchant_id": int(merchant_id),
        "device_id": int(RNG.integers(1, 5_000_000)),
        "bank": str(bank),
        "payment_rail": str(rail),
        "region": str(region),
        "merchant_category": str(category),
        "gateway": str(gateway),
        "payment_method": str(method),
        "amount": amount,
        "currency": CURRENCY,
        "authorization_status": status,
        "response_code": str(resp_code),
        "settlement_status": "SETTLED" if is_success else "NOT_SETTLED",
        "fraud_score": round(float(RNG.beta(2, 20)), 4),
        "latency_ms": round(latency, 2),
        "is_synthetic_incident": 1 if is_incident_target else 0,
    }


# ---------------------------------------------------------------------------
# Producer loop
# ---------------------------------------------------------------------------

def produce_loop(bootstrap_servers: str, topic: str, rate: int):
    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        linger_ms=50,
        batch_size=64 * 1024,
    )
    interval = 1.0 / rate
    print(f"Producing to '{topic}' at ~{rate} events/sec...")
    while True:
        t0 = time.time()
        event = make_event()
        producer.send(topic, event)
        elapsed = time.time() - t0
        sleep_for = interval - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)


# ---------------------------------------------------------------------------
# Control API
# ---------------------------------------------------------------------------

app = FastAPI()


@app.post("/incident/start")
def start_incident():
    injector.start()
    return {"message": "Incident injection started", **injector.status()}


@app.post("/incident/stop")
def stop_incident():
    injector.stop()
    return {"message": "Incident injection stopped", **injector.status()}


@app.get("/incident/status")
def incident_status():
    return injector.status()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    parser.add_argument("--topic", default="transactions")
    parser.add_argument("--rate", type=int, default=2000, help="events/sec")
    parser.add_argument("--api-port", type=int, default=8001)
    parser.add_argument("--ch-host", default="localhost")
    parser.add_argument("--ch-port", type=int, default=8123)
    parser.add_argument("--ch-database", default="bank_demo")
    parser.add_argument("--ch-user", default="demo")
    parser.add_argument("--ch-password", default="demo_pass")
    args = parser.parse_args()

    global CATALOG
    print("Loading merchant catalog...")
    ch_client = clickhouse_connect.get_client(
        host=args.ch_host, port=args.ch_port, database=args.ch_database,
        username=args.ch_user, password=args.ch_password,
    )
    CATALOG = MerchantCatalog(ch_client)
    print(f"Catalog loaded: {sum(len(v['ids']) for v in CATALOG.by_category.values()):,} merchants "
          f"across {len(CATALOG.by_category)} categories")

    producer_thread = threading.Thread(
        target=produce_loop,
        args=(args.bootstrap_servers, args.topic, args.rate),
        daemon=True,
    )
    producer_thread.start()

    uvicorn.run(app, host="0.0.0.0", port=args.api_port)


if __name__ == "__main__":
    main()