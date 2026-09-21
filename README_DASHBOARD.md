# Banking Control Tower — Real-Time ClickHouse & React Dashboard

Real-time executive and operations analytics dashboard built with **React**, **Chart.js**, and **Tailwind CSS**, powered by a high-throughput **ClickHouse** analytical database receiving streaming transactions from **Kafka**.

---

## 🚀 Architecture Overview

```text
Synthetic Producer / Kafka Stream
              │
              ▼
   ClickHouse Kafka Engine
   (transactions_kafka_queue)
              │
      Materialized View
  (mv_kafka_to_transactions)
              │
              ▼
    ClickHouse MergeTree
  (transactions & 1m aggregates)
              │
              ▼
     FastAPI Backend (:8000)
 (Analytical Queries & WebSockets)
              │
              ▼
  React + Chart.js Dashboard (:5173)
 (Live Visualizations & Drill-Downs)
```

---

## 📊 Features

1. **Top-Level KPI Strip**:
   - Total volume in USD ($) and transaction count with window-over-window velocity delta (e.g. ▲ 8.7%).
   - Global authorization success rate % with real-time SLA threshold monitoring.
   - Average and p95 latency tracking.
   - Merchant network footprint and fraud risk scoring.

2. **Continuous Anomaly Detection**:
   - Compares live 15-minute slice metrics against trailing 24-hour baselines directly in ClickHouse.
   - Surfaces slices deviating by &gt;1.8x from their historical norm (e.g., `Card / Georgia / E-commerce / Gateway Y`).
   - Interactive **"Investigate Slice"** button jumps directly into the multi-dimensional explorer.

3. **Chart.js Real-Time Visualizations**:
   - **Transaction Velocity & Failures**: Smooth area/line chart rendering total throughput and failed transactions per minute.
   - **Success Rate & Latency Trend**: Dual-axis line chart correlating failure spikes with latency degradation.
   - **Gateway Health**: Comparative bar chart showing failure rate % and latency per gateway.
   - **Payment Rail Mix**: High-contrast doughnut chart tracking volume across Card, ACH, Wire, Zelle, PayPal.
   - **Root Cause Analysis**: Horizontal bar chart breaking down failure response codes (e.g., `91 - System Error`, `96 - Gateway Timeout`, `51 - Insufficient Funds`).

4. **Multi-Dimensional Drill-Down Explorer**:
   - Explore performance across Bank &rarr; Rail &rarr; Region &rarr; Category &rarr; Gateway &rarr; Affected Merchants.
   - Clickable breadcrumbs and slice filtering.

5. **Live Ingested Transaction Feed**:
   - Scrolling real-time table of recent events ingested from ClickHouse with status badges, latencies, and response codes.

6. **Interactive Incident Simulation**:
   - Built-in **"Inject Incident"** / **"Resolve Incident"** control.
   - Ramps failure rates and latency on Gateway Y over 30 seconds, allowing full end-to-end demonstration of anomaly detection and recovery.

7. **Resilient Dual-Mode Connectivity**:
   - Automatically connects to live ClickHouse (`localhost:8123`) when available.
   - Features a zero-setup fallback stream simulator so the dashboard can be demonstrated immediately even before launching Docker containers.

---

## 🛠️ Quick Start

### 1. Install Python dependencies
```bash
pip install -r backend/requirements.txt
```

### 2. Start ClickHouse & Kafka (Optional / Docker)
If Docker Desktop is running:
```bash
docker compose up -d
```
This also starts ClickStack Local Mode. Open HyperDX directly at `http://localhost:8080`. ClickStack's OpenTelemetry HTTP endpoint is `http://localhost:4318`.

The producer exports one sampled transaction per 100 events to ClickStack as OTLP logs. In HyperDX, add an `otel_logs` source if prompted, then search for `service.name:bank-control-tower-producer`. Override the default sampling or collector URL with `--clickstack-sample-every` and `--clickstack-endpoint` when needed.

For an existing ClickHouse volume, apply `init/06_performance_aggregates.sql` once after updating the repository. It creates the time-first and slice-ordered raw projections plus the minute-level slice and merchant aggregates used by the dashboard. Do not rerun its historical backfill after the aggregate tables have been populated.
Initialize the dimensions required by the transaction generators:
```bash
python populate_dimensions.py
```

Generate historical baseline traffic (needed for meaningful anomaly comparisons):
```bash
python generate_baseline.py --rows 500000
```

Start the live Kafka producer and its incident-control API in a separate terminal:
```bash
python producer.py
```

### 3. Start the FastAPI Real-Time Backend
In the project root:
```bash
python -m backend.main
```
The backend will run on `http://localhost:8000` with WebSocket endpoint at `ws://localhost:8000/ws/live`.

### 4. Start the React + Chart.js Frontend
In another terminal:
```bash
cd frontend
npm run dev
```
Open `http://localhost:5173` in your browser.

To open the dashboard from another machine on the same network, use the host
machine's address rather than `localhost`. The frontend automatically connects
to the backend on that same host at port 8000. Set `VITE_API_BASE` before
building only when the API is hosted elsewhere.

### Optional: Langfuse observability

Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` before starting the backend
or running `ml_anomaly.py`. Set `LANGFUSE_BASE_URL` as well for a self-hosted
instance. The integration traces anomaly detection, slice investigation, and
ML training using only aggregate metrics and selected dimensions; it never
exports transaction rows or customer identifiers. Without these variables,
Langfuse is disabled and the application runs normally.

---

## ⚡ Simulating an Incident During a Demo
Click the **"INJECT INCIDENT (GATEWAY Y)"** button in the header (or send a POST request):
```bash
curl -X POST http://localhost:8000/incident/start
```
Within seconds:
- Gateway Y failure rate will ramp up.
- The **⚠ CRITICAL ANOMALY DETECTED** banner will trigger.
- The Chart.js velocity and latency charts will display the spike.
- Click **"Investigate Slice"** to view affected merchants.
- Click **"Resolve Incident"** to restore system metrics to normal baseline.

Before the demo, confirm the fault injector is running a 30-second ramp (not the
old 300-second class left over from a stale producer process):
```bash
curl http://localhost:8000/incident/status   # expect "ramp_seconds": 30
```
Restart the producer (`python producer.py`) if it reports anything else, then
re-check the status — restarting resets the incident automatically.
