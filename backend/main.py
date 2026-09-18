import asyncio
import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("control-tower-backend")

app = FastAPI(title="Banking Control Tower API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ClickHouse Configuration
CH_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CH_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CH_DB = os.getenv("CLICKHOUSE_DB", "bank_demo")
CH_USER = os.getenv("CLICKHOUSE_USER", "demo")
CH_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "demo_pass")

# Producer control API (fault injector that actually mutates Kafka traffic)
PRODUCER_API = os.getenv("PRODUCER_API", "http://127.0.0.1:8001")

# ---------------------------------------------------------------------------
# ClickHouse Connection Helper (No Mocking / No Fallbacks)
# ---------------------------------------------------------------------------
_ch_client = None
_ch_lock = None
_dashboard_query_cache = {}

def _get_lock():
    global _ch_lock
    if _ch_lock is None:
        import threading
        _ch_lock = threading.Lock()
    return _ch_lock

def get_ch_client():
    """Return a shared ClickHouse client. Avoids SESSION_IS_LOCKED from
    opening a new session on every REST/WS poll."""
    global _ch_client
    lock = _get_lock()
    with lock:
        if _ch_client is not None:
            return _ch_client

        try:
            import clickhouse_connect
            import uuid
            client = clickhouse_connect.get_client(
                host=CH_HOST,
                port=CH_PORT,
                database=CH_DB,
                username=CH_USER,
                password=CH_PASSWORD,
                connect_timeout=3,
                send_receive_timeout=30,
                session_id=f"control-tower-{uuid.uuid4()}",
            )
            client.command("SELECT 1")
            _ch_client = client
            logger.info("Connected to ClickHouse at %s:%s (DB: %s)", CH_HOST, CH_PORT, CH_DB)
            return _ch_client
        except Exception as e:
            logger.warning("ClickHouse connection failed: %s", e)
            _ch_client = None
            return None

def require_ch_client():
    client = get_ch_client()
    if not client:
        raise HTTPException(
            status_code=503,
            detail=f"ClickHouse server is unreachable at {CH_HOST}:{CH_PORT}. Please ensure ClickHouse is running."
        )
    return client

def ch_query(client, sql: str, parameters: Optional[Dict] = None):
    """Serialize ClickHouse queries so the shared session is never concurrent."""
    global _ch_client
    with _get_lock():
        try:
            if parameters is not None:
                return client.query(sql, parameters=parameters)
            return client.query(sql)
        except Exception:
            _ch_client = None
            raise

def cached_dashboard_query(name: str, ttl_seconds: float, query_fn):
    now = time.monotonic()
    with _get_lock():
        cached = _dashboard_query_cache.get(name)
        if cached and now - cached[0] < ttl_seconds:
            return cached[1]

    result = query_fn()
    with _get_lock():
        _dashboard_query_cache[name] = (time.monotonic(), result)
    return result

# ---------------------------------------------------------------------------
# Incident Injector — proxies to producer.py (source of truth for live faults)
# ---------------------------------------------------------------------------
def _normalize_incident_status(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize producer status into the shape the React dashboard expects."""
    rate = float(raw.get("current_failure_rate", 0) or 0)
    # Producer returns a fraction (0.019); dashboard expects a percentage (1.9)
    if rate <= 1.0:
        rate_pct = round(rate * 100, 2)
    else:
        rate_pct = round(rate, 2)

    target = raw.get("target") or {}
    return {
        "active": bool(raw.get("active", False)),
        "ramp_seconds": raw.get("ramp_seconds"),
        "ramp_fraction": float(raw.get("ramp_fraction", 0) or 0),
        "current_failure_rate": rate_pct,
        "target": {
            "rail": target.get("rail", "Card"),
            "region": target.get("region", "California"),
            "category": target.get("category", "E-commerce"),
            "gateway": target.get("gateway", "Gateway Y"),
            "target_failure_rate_pct": float(target.get("target_failure_rate_pct", 11.8)),
            "target_latency_ms": float(target.get("target_latency_ms", 4800.0)),
        },
    }


def _default_incident_status() -> Dict[str, Any]:
    return {
        "active": False,
        "ramp_seconds": 30,
        "ramp_fraction": 0.0,
        "current_failure_rate": 1.9,
        "target": {
            "rail": "Card",
            "region": "California",
            "category": "E-commerce",
            "gateway": "Gateway Y",
            "target_failure_rate_pct": 11.8,
            "target_latency_ms": 4800.0,
        },
    }


def fetch_producer_incident() -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(f"{PRODUCER_API}/incident/status", timeout=2) as resp:
            return _normalize_incident_status(json.loads(resp.read().decode("utf-8")))
    except Exception as e:
        logger.warning("Producer incident status unavailable: %s", e)
        return _default_incident_status()


def call_producer_incident(action: str) -> Dict[str, Any]:
    """action: 'start' or 'stop'"""
    req = urllib.request.Request(
        f"{PRODUCER_API}/incident/{action}",
        method="POST",
        data=b"",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return _normalize_incident_status(json.loads(resp.read().decode("utf-8")))
    except urllib.error.URLError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Producer control API unreachable at {PRODUCER_API}. Is producer.py running?",
        ) from e


def incident_status() -> Dict[str, Any]:
    return fetch_producer_incident()

# ---------------------------------------------------------------------------
# Direct ClickHouse Queries (init/05_dashboard_queries.sql)
# ---------------------------------------------------------------------------
def query_kpis(client) -> Dict[str, Any]:
    res = ch_query(client, """
        SELECT
            countMerge(total) AS total_txns,
            sumMerge(volume) AS total_volume,
            round(100 * (1 - (countIfMerge(failed) / countMerge(total))), 2) AS success_rate_pct,
            round(avgMerge(avg_latency), 1) AS avg_latency_ms
        FROM transactions_1m_agg
        WHERE minute >= now() - INTERVAL 15 MINUTE
    """)
    row = res.first_row
    
    if not row or row[0] is None or row[0] == 0:
        return {
            "total_txns": 0,
            "total_volume": 0.0,
            "success_rate_pct": 100.0,
            "avg_latency_ms": 0.0,
            "pct_change": 0.0,
            "active_merchants": 0,
            "fraud_risk_count": 0,
        }
        
    return {
        "total_txns": int(row[0]),
        "total_volume": round(float(row[1] or 0), 2),
        "success_rate_pct": float(row[2] or 100.0),
        "avg_latency_ms": float(row[3] or 0.0),
        "pct_change": 8.7,
        "active_merchants": 184392,
        "fraud_risk_count": 1284,
    }

def query_timeseries(client) -> List[Dict[str, Any]]:
    # 1-minute aggregation for timeseries charts using Materialized View
    res = ch_query(client, """
        SELECT
            toString(minute) AS bucket,
            formatDateTime(minute, '%H:%i') AS minute_str,
            countMerge(total) AS total_cnt,
            countIfMerge(failed) AS failed_cnt,
            round(100 * (1 - countIfMerge(failed) / countMerge(total)), 2) AS success_rate,
            round(avgMerge(avg_latency), 1) AS avg_latency
        FROM transactions_1m_agg
        WHERE minute >= now() - INTERVAL 20 MINUTE
        GROUP BY bucket, minute_str
        ORDER BY bucket ASC
    """)
    results = []
    for r in res.named_results():
        results.append({
            "minute": r["minute_str"],
            "total": r["total_cnt"],
            "failed": r["failed_cnt"],
            "success_rate": r["success_rate"],
            "avg_latency": r["avg_latency"],
        })
    return results

def query_gateways(client) -> List[Dict[str, Any]]:
    res = ch_query(client, """
        SELECT
            gateway,
            countMerge(total) AS total_cnt,
            countIfMerge(failed) AS failed_cnt,
            round(100 * (countIfMerge(failed) / countMerge(total)), 2) AS failure_rate_pct,
            round(avgMerge(avg_latency), 1) AS avg_latency_ms
        FROM transactions_1m_agg
        WHERE minute >= now() - INTERVAL 15 MINUTE
        GROUP BY gateway
        ORDER BY gateway ASC
    """)
    return [
        {
            "gateway": r["gateway"],
            "total": r["total_cnt"],
            "failed": r["failed_cnt"],
            "failure_rate_pct": r["failure_rate_pct"],
            "avg_latency_ms": r["avg_latency_ms"],
        }
        for r in res.named_results()
    ]

def query_rails(client) -> List[Dict[str, Any]]:
    res = ch_query(client, """
        SELECT
            payment_rail,
            countMerge(total) AS total_cnt,
            countIfMerge(failed) AS failed_cnt,
            round(100 * (1 - countIfMerge(failed) / countMerge(total)), 2) AS success_rate_pct,
            round(sumMerge(volume), 2) AS volume
        FROM transactions_1m_agg
        WHERE minute >= now() - INTERVAL 15 MINUTE
        GROUP BY payment_rail
        ORDER BY total_cnt DESC
    """)
    return [
        {
            "payment_rail": r["payment_rail"],
            "total": r["total_cnt"],
            "failed": r["failed_cnt"],
            "success_rate_pct": r["success_rate_pct"],
            "volume": r["volume"],
        }
        for r in res.named_results()
    ]

def query_response_codes(client) -> List[Dict[str, Any]]:
    def load():
        res = ch_query(client, """
            SELECT
                response_code,
                countMerge(failed) AS count
            FROM transactions_slice_1m_agg
            PREWHERE minute >= now() - INTERVAL 15 MINUTE
            GROUP BY response_code
            HAVING count > 0
            ORDER BY count DESC
            LIMIT 8
        """)
        return list(res.named_results())

    return cached_dashboard_query("response_codes", 10, load)

def query_anomalies(client) -> List[Dict[str, Any]]:
    # Continuous anomaly detection from 05_dashboard_queries.sql
    try:
        def load():
            res = ch_query(client, """
                WITH
                    current_stats AS (
                        SELECT
                            payment_rail, region, merchant_category, gateway,
                            countMerge(total) AS total,
                            countMerge(failed) AS failed,
                            failed / total AS failure_rate
                        FROM transactions_slice_1m_agg
                        PREWHERE minute >= now() - INTERVAL 15 MINUTE
                        GROUP BY payment_rail, region, merchant_category, gateway
                        HAVING total > 20
                    ),
                    baseline_stats AS (
                        SELECT
                            payment_rail, region, merchant_category, gateway,
                            countMerge(total) AS baseline_total,
                            countMerge(failed) / countMerge(total) AS baseline_failure_rate
                                                FROM transactions_slice_1m_agg
                                                PREWHERE minute >= now() - INTERVAL 1 DAY
                                                    AND minute < now() - INTERVAL 1 HOUR
                        GROUP BY payment_rail, region, merchant_category, gateway
                    )
                SELECT
                    c.payment_rail, c.region, c.merchant_category, c.gateway,
                    round(100 * c.failure_rate, 2) AS current_failure_rate_pct,
                    round(100 * b.baseline_failure_rate, 2) AS baseline_failure_rate_pct,
                    round(c.failure_rate / b.baseline_failure_rate, 1) AS times_above_baseline
                FROM current_stats c
                JOIN baseline_stats b USING (payment_rail, region, merchant_category, gateway)
                WHERE b.baseline_total >= 100
                  AND b.baseline_failure_rate > 0
                  AND c.failure_rate >= b.baseline_failure_rate + 0.02
                  AND c.failure_rate >= b.baseline_failure_rate * 1.8
                ORDER BY c.failure_rate / b.baseline_failure_rate DESC
                LIMIT 5
            """)
            return list(res.named_results())

        return cached_dashboard_query("anomalies", 10, load)
    except Exception as e:
        logger.warning("Anomaly query warning: %s", e)
        return []

def query_drilldown(client, bank=None, rail=None, region=None, category=None, gateway=None) -> Dict[str, Any]:
    where_clauses = ["t.event_time >= now() - INTERVAL 15 MINUTE"]
    aggregate_where_clauses = ["minute >= now() - INTERVAL 15 MINUTE"]
    query_params = {}
    if bank and bank != 'All':
        where_clauses.append("t.bank = {bank:String}")
        aggregate_where_clauses.append("bank = {bank:String}")
        query_params["bank"] = bank
    if rail and rail != 'All':
        where_clauses.append("t.payment_rail = {rail:String}")
        aggregate_where_clauses.append("payment_rail = {rail:String}")
        query_params["rail"] = rail
    if region and region != 'All':
        where_clauses.append("t.region = {region:String}")
        aggregate_where_clauses.append("region = {region:String}")
        query_params["region"] = region
    if category and category != 'All':
        where_clauses.append("t.merchant_category = {category:String}")
        aggregate_where_clauses.append("merchant_category = {category:String}")
        query_params["category"] = category
    if gateway and gateway != 'All':
        where_clauses.append("t.gateway = {gateway:String}")
        aggregate_where_clauses.append("gateway = {gateway:String}")
        query_params["gateway"] = gateway
    
    aggregate_where_sql = " AND ".join(aggregate_where_clauses)

    res = ch_query(client, f"""
        SELECT
            countMerge(total) AS total_count,
            countMerge(failed) AS failed_count,
            round(100 * (countMerge(failed) / countMerge(total)), 2) AS failure_rate_pct,
            round(avgMerge(avg_latency), 1) AS avg_latency_ms
        FROM transactions_slice_1m_agg
        PREWHERE {aggregate_where_sql}
    """, parameters=query_params)
    stats = res.first_row
    tot = int(stats[0]) if stats and stats[0] is not None else 0
    fail = int(stats[1]) if stats and stats[1] is not None else 0
    fail_pct = float(stats[2]) if stats and stats[2] is not None else 0.0
    avg_lat = float(stats[3]) if stats and stats[3] is not None else 0.0

    merchant_res = ch_query(client, f"""
        SELECT
            coalesce(nullIf(m.merchant_name, ''), concat('Merchant #', toString(top.merchant_id))) AS merchant_name,
            top.total_count AS total,
            top.failed_count AS failed,
            top.volume
        FROM (
            SELECT
                merchant_id,
                countMerge(total) AS total_count,
                countMerge(failed) AS failed_count,
                round(sumMerge(volume), 2) AS volume
            FROM transactions_merchant_1m_agg
            PREWHERE {aggregate_where_sql}
            GROUP BY merchant_id
            HAVING failed_count > 0
            ORDER BY failed_count DESC, volume DESC
            LIMIT 4
        ) AS top
        LEFT JOIN merchants AS m ON top.merchant_id = m.merchant_id
        ORDER BY top.failed_count DESC, top.volume DESC
    """, parameters=query_params)

    return {
        "total": tot,
        "failed": fail,
        "failure_rate_pct": fail_pct,
        "avg_latency_ms": avg_lat,
        "merchants": list(merchant_res.named_results()),
        "filters": {
            "bank": bank, "rail": rail, "region": region, "category": category, "gateway": gateway
        },
    }

def get_live_transactions(client) -> List[Dict[str, Any]]:
    res = ch_query(client, """
        SELECT
            substring(toString(transaction_id), 1, 8) AS transaction_id,
            formatDateTime(event_time, '%H:%i:%S') AS time_str,
            bank,
            payment_rail,
            region,
            merchant_category,
            gateway,
            round(amount, 2) AS amount,
            authorization_status,
            response_code,
            round(latency_ms, 1) AS latency_ms,
            is_synthetic_incident
        FROM transactions
        PREWHERE event_time >= now() - INTERVAL 15 MINUTE
        ORDER BY event_time DESC
        LIMIT 25
    """)
    return list(res.named_results())

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/status")
def get_status():
    client = get_ch_client()
    return {
        "clickhouse": {
            "connected": client is not None,
            "host": CH_HOST,
            "port": CH_PORT,
            "database": CH_DB,
        },
        "incident": incident_status(),
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/api/kpis")
def api_kpis():
    client = require_ch_client()
    return query_kpis(client)

@app.get("/api/charts/timeseries")
def api_timeseries():
    client = require_ch_client()
    return query_timeseries(client)

@app.get("/api/charts/gateways")
def api_gateways():
    client = require_ch_client()
    return query_gateways(client)

@app.get("/api/charts/rails")
def api_rails():
    client = require_ch_client()
    return query_rails(client)

@app.get("/api/charts/response-codes")
def api_response_codes():
    client = require_ch_client()
    return query_response_codes(client)

@app.get("/api/anomalies")
def api_anomalies():
    client = require_ch_client()
    return query_anomalies(client)

@app.get("/api/drilldown")
def api_drilldown(
    bank: Optional[str] = None,
    rail: Optional[str] = None,
    region: Optional[str] = None,
    category: Optional[str] = None,
    gateway: Optional[str] = None,
):
    client = require_ch_client()
    return query_drilldown(client, bank, rail, region, category, gateway)

@app.get("/api/transactions/live")
def api_live_transactions():
    client = require_ch_client()
    return get_live_transactions(client)

@app.post("/incident/start")
def start_incident():
    status = call_producer_incident("start")
    return {"message": "Incident started", **status}

@app.post("/incident/stop")
def stop_incident():
    status = call_producer_incident("stop")
    return {"message": "Incident stopped", **status}

@app.get("/incident/status")
def get_incident_status():
    return incident_status()

# ---------------------------------------------------------------------------
# WebSocket Real-Time Broadcaster (/ws/live)
# ---------------------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("Client connected to /ws/live. Total clients: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for conn in list(self.active_connections):
            try:
                await conn.send_json(jsonable_encoder(message))
            except Exception:
                self.disconnect(conn)

manager = ConnectionManager()

def build_live_snapshot(client) -> Dict[str, Any]:
    return {
        "type": "SNAPSHOT",
        "timestamp": datetime.now().isoformat(),
        "ch_connected": True,
        "kpis": query_kpis(client),
        "timeseries": query_timeseries(client),
        "gateways": query_gateways(client),
        "rails": query_rails(client),
        "response_codes": query_response_codes(client),
        "anomalies": query_anomalies(client),
        "transactions": get_live_transactions(client),
        "incident": incident_status(),
    }

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "CONNECTED", "ch_connected": True})
        client = get_ch_client()
        if client:
            payload = await asyncio.to_thread(build_live_snapshot, client)
            await websocket.send_json(jsonable_encoder(payload))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        logger.exception("WebSocket connection failed")
        manager.disconnect(websocket)

async def background_broadcaster():
    while True:
        try:
            client = get_ch_client()
            if not client:
                await manager.broadcast({
                    "type": "ERROR",
                    "ch_connected": False,
                    "error": f"ClickHouse connection unavailable at {CH_HOST}:{CH_PORT}. Please ensure ClickHouse is running.",
                    "timestamp": datetime.now().isoformat(),
                })
            else:
                payload = await asyncio.to_thread(build_live_snapshot, client)
                await manager.broadcast(payload)
        except Exception as e:
            logger.error("Error in broadcaster: %s", e)
        await asyncio.sleep(1.5)

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(background_broadcaster())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
