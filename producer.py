"""
Live transaction producer — Banking Control Tower demo.

Streams synthetic transaction events to Kafka in real time, at a target
rate. Reuses the same distributions as generate_baseline.py so live data
and history look like one system.

Includes a small FastAPI control surface to start/stop/ramp the fault
injector during the live demo:

    POST /incident/start   -> begins ramping the incident in over ~30 sec
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
from queue import Empty, Full, Queue
from urllib.error import URLError
from urllib.request import Request, urlopen

import numpy as np
from kafka import KafkaProducer
from fastapi import FastAPI
import uvicorn

import clickhouse_connect
from clickhouse_connect.driver.exceptions import OperationalError

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


class ClickStackExporter:
    """Batch a sampled transaction stream into ClickStack OTLP logs."""

    def __init__(self, endpoint: str, sample_every: int = 100):
        self.endpoint = endpoint
        self.sample_every = max(1, sample_every)
        self.events = Queue(maxsize=2000)
        self._submitted = 0
        self._last_error_at = 0.0

    def start(self):
        threading.Thread(target=self._run, name="clickstack-exporter", daemon=True).start()

    def submit(self, event: dict):
        self._submitted += 1
        if self._submitted % self.sample_every != 0:
            return
        try:
            self.events.put_nowait(event)
        except Full:
            pass

    def _run(self):
        while True:
            batch = []
            try:
                batch.append(self.events.get(timeout=1.0))
            except Empty:
                continue

            while len(batch) < 100:
                try:
                    batch.append(self.events.get_nowait())
                except Empty:
                    break

            try:
                payload = {
                    "resourceLogs": [{
                        "resource": {"attributes": [
                            {"key": "service.name", "value": {"stringValue": "bank-control-tower-producer"}},
                            {"key": "service.namespace", "value": {"stringValue": "fintech-demo"}},
                        ]},
                        "scopeLogs": [{
                            "scope": {"name": "banking-transactions"},
                            "logRecords": [
                                {
                                    "timeUnixNano": str(time.time_ns()),
                                    "severityText": "ERROR" if event["authorization_status"] == "FAILED" else "INFO",
                                    "body": {"stringValue": json.dumps(event)},
                                    "attributes": [
                                        {"key": key, "value": {"stringValue": str(event[key])}}
                                        for key in ("transaction_id", "bank", "payment_rail", "region", "merchant_category", "gateway", "authorization_status", "response_code", "latency_ms", "amount")
                                    ],
                                }
                                for event in batch
                            ],
                        }],
                    }]
                }
                request = Request(
                    self.endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5):
                    pass
            except (OSError, URLError) as exc:
                now = time.time()
                if now - self._last_error_at > 30:
                    print(f"ClickStack telemetry unavailable at {self.endpoint}: {exc}")
                    self._last_error_at = now


def connect_clickhouse_with_retry(args, attempts: int = 12, delay_seconds: float = 2.0):
    """Wait for ClickHouse to finish starting before loading the catalog."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return clickhouse_connect.get_client(
                host=args.ch_host, port=args.ch_port, database=args.ch_database,
                username=args.ch_user, password=args.ch_password,
            )
        except OperationalError as exc:
            last_error = exc
            if attempt == attempts:
                break
            print(f"ClickHouse is not ready (attempt {attempt}/{attempts}); retrying in {delay_seconds:g}s...")
            time.sleep(delay_seconds)

    raise RuntimeError(
        f"Unable to connect to ClickHouse at {args.ch_host}:{args.ch_port} "
        f"after {attempts} attempts. Check that the ClickHouse container is healthy."
    ) from last_error


# ---------------------------------------------------------------------------
# Fault injector — runtime-controllable via the API below
# ---------------------------------------------------------------------------

class FaultInjector:
    """
    Targets: Card / California / E-commerce / Gateway Y, per the demo brief.
    Ramps failure rate + latency in over `ramp_seconds` rather than
    stepping instantly, so the dashboard visibly climbs on screen.
    """

    def __init__(self, ramp_seconds: int = 30):
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
            "ramp_seconds": self.ramp_seconds,
            "ramp_fraction": round(self._ramp_fraction(), 3),
            "current_failure_rate": round(self.current_failure_rate(), 4),
            "target": {
                "rail": self.rail, "region": self.region,
                "category": self.category, "gateway": self.gateway,
                "target_failure_rate_pct": round(self.target_failure_rate * 100, 2),
                "target_latency_ms": self.target_latency_ms,
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

def produce_loop(bootstrap_servers: str, topic: str, rate: int, clickstack_exporter: ClickStackExporter):
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
        clickstack_exporter.submit(event)
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
    parser.add_argument("--clickstack-endpoint", default="http://localhost:4318/v1/logs")
    parser.add_argument("--clickstack-sample-every", type=int, default=100, help="Send one transaction to ClickStack for every N events")
    args = parser.parse_args()

    global CATALOG
    print("Loading merchant catalog...")
    ch_client = connect_clickhouse_with_retry(args)
    CATALOG = MerchantCatalog(ch_client)
    print(f"Catalog loaded: {sum(len(v['ids']) for v in CATALOG.by_category.values()):,} merchants "
          f"across {len(CATALOG.by_category)} categories")

    clickstack_exporter = ClickStackExporter(
        endpoint=args.clickstack_endpoint,
        sample_every=args.clickstack_sample_every,
    )
    clickstack_exporter.start()

    producer_thread = threading.Thread(
        target=produce_loop,
        args=(args.bootstrap_servers, args.topic, args.rate, clickstack_exporter),
        daemon=True,
    )
    producer_thread.start()

    uvicorn.run(app, host="0.0.0.0", port=args.api_port)


if __name__ == "__main__":
    main()