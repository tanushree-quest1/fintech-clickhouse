import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Header } from './components/Header';
import { KpiStrip } from './components/KpiStrip';
import { AnomalyBanner } from './components/AnomalyBanner';
import { VelocityChart } from './components/charts/VelocityChart';
import { SuccessLatencyChart } from './components/charts/SuccessLatencyChart';
import { GatewayHealthChart } from './components/charts/GatewayHealthChart';
import { RailDistributionChart } from './components/charts/RailDistributionChart';
import { ResponseCodesChart } from './components/charts/ResponseCodesChart';
import { DrillDownExplorer } from './components/DrillDownExplorer';
import { LiveTransactionsTable } from './components/LiveTransactionsTable';
import { ErrorNotice } from './components/ErrorNotice';
import { AIAnalystButton } from './components/AIAnalystPanel';
import {
  KpiData,
  TimeseriesPoint,
  GatewayMetric,
  RailMetric,
  ResponseCodeMetric,
  AnomalyItem,
  TransactionItem,
  IncidentStatus,
} from './types';
import { API_BASE, WS_URL } from './api';

export const App: React.FC = () => {
  const [chConnected, setChConnected] = useState<boolean>(false);
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [refreshInterval, setRefreshInterval] = useState<number>(2); // seconds
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Core Real-Time State
  const [kpis, setKpis] = useState<KpiData | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);
  const [gateways, setGateways] = useState<GatewayMetric[]>([]);
  const [rails, setRails] = useState<RailMetric[]>([]);
  const [responseCodes, setResponseCodes] = useState<ResponseCodeMetric[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([]);
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [incident, setIncident] = useState<IncidentStatus | null>(null);

  // Investigating slice state
  const [investigatingSlice, setInvestigatingSlice] = useState<{
    rail?: string;
    region?: string;
    category?: string;
    gateway?: string;
  } | null>(null);

  const wsRef = useRef<WebSocket | null>(null);

  // Apply snapshot payload
  const handleSnapshot = useCallback((data: any) => {
    if (data.type === 'ERROR') {
      setWsConnected(false);
      return;
    }

    if (data.type === 'SNAPSHOT') {
      setChConnected(data.ch_connected);
      setErrorMessage(null);
      if (data.kpis) setKpis(data.kpis);
      if (data.timeseries) setTimeseries(data.timeseries);
      if (data.gateways) setGateways(data.gateways);
      if (data.rails) setRails(data.rails);
      if (data.response_codes) setResponseCodes(data.response_codes);
      if (data.anomalies) setAnomalies(data.anomalies);
      if (data.transactions) setTransactions(data.transactions);
      if (data.incident) setIncident(data.incident);
    }
  }, []);

  // REST fetch
  const fetchAllData = useCallback(async () => {
    try {
      setIsRefreshing(true);
      const statusRes = await fetch(`${API_BASE}/api/status`).then((r) => r.json()).catch(() => null);

      if (!statusRes || !statusRes.clickhouse?.connected) {
        setChConnected(false);
        setErrorMessage(
          statusRes?.detail ||
          'ClickHouse is not running or backend cannot connect to localhost:8123 (database: bank_demo).'
        );
        return;
      }

      setChConnected(true);
      setErrorMessage(null);
      if (statusRes.incident) setIncident(statusRes.incident);

      const fetchJson = async <T,>(path: string, fallback: T): Promise<T> => {
        try {
          const response = await fetch(`${API_BASE}${path}`);
          return response.ok ? await response.json() : fallback;
        } catch {
          return fallback;
        }
      };

      const [kpiRes, tsRes, gwRes, railRes, respRes, anomRes, txnRes] =
        await Promise.all([
          fetchJson<KpiData | null>('/api/kpis', null),
          fetchJson<TimeseriesPoint[]>('/api/charts/timeseries', []),
          fetchJson<GatewayMetric[]>('/api/charts/gateways', []),
          fetchJson<RailMetric[]>('/api/charts/rails', []),
          fetchJson<ResponseCodeMetric[]>('/api/charts/response-codes', []),
          fetchJson<AnomalyItem[]>('/api/anomalies', []),
          fetchJson<TransactionItem[]>('/api/transactions/live', []),
        ]);

      if (kpiRes) setKpis(kpiRes);
      if (tsRes) setTimeseries(tsRes);
      if (gwRes) setGateways(gwRes);
      if (railRes) setRails(railRes);
      if (respRes) setResponseCodes(respRes);
      if (anomRes) setAnomalies(anomRes);
      if (txnRes) setTransactions(txnRes);
    } catch (err: any) {
      console.error('Error in manual/interval fetch:', err);
      setChConnected(false);
      setErrorMessage('Backend service is offline or unreachable at http://localhost:8000.');
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  // WebSocket lifecycle
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: any = null;

    const connectWs = () => {
      try {
        ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            handleSnapshot(data);
          } catch (e) {
            console.error('Error parsing WS message:', e);
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
          reconnectTimeout = setTimeout(connectWs, 3000);
        };

        ws.onerror = () => {
          ws?.close();
        };
      } catch (err) {
        setWsConnected(false);
        reconnectTimeout = setTimeout(connectWs, 3000);
      }
    };

    connectWs();
    fetchAllData();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, [handleSnapshot, fetchAllData]);

  // Periodic polling fallback or manual interval sync
  useEffect(() => {
    if (refreshInterval <= 0) return;

    const interval = setInterval(() => {
      if (!wsConnected || !chConnected) {
        fetchAllData();
      }
    }, refreshInterval * 1000);

    return () => clearInterval(interval);
  }, [refreshInterval, wsConnected, chConnected, fetchAllData]);

  // Fault injection toggle
  const handleToggleIncident = async () => {
    const isCurrentlyActive = incident?.active;
    const endpoint = isCurrentlyActive ? '/incident/stop' : '/incident/start';
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
      const data = await res.json();
      setIncident(data);
      fetchAllData();
    } catch (err) {
      console.error('Failed to toggle incident:', err);
    }
  };

  const handleInvestigate = (anomaly: AnomalyItem) => {
    setInvestigatingSlice({
      rail: anomaly.payment_rail,
      region: anomaly.region,
      category: anomaly.merchant_category,
      gateway: anomaly.gateway,
    });
    const el = document.getElementById('drill-down-section');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-white text-gray-900 flex flex-col font-['Plus_Jakarta_Sans',sans-serif]">
      {/* Top Sticky Header */}
      <Header
        chConnected={chConnected}
        wsConnected={wsConnected}
        incident={incident}
        refreshInterval={refreshInterval}
        onIntervalChange={setRefreshInterval}
        onManualRefresh={fetchAllData}
        onToggleIncident={handleToggleIncident}
        isRefreshing={isRefreshing}
      />

      {/* Main Dashboard Body */}
      <main className="flex-1 p-6 space-y-6 max-w-[1700px] w-full mx-auto bg-white">
        {/* If backend or ClickHouse is offline, display error message */}
        {(!chConnected || errorMessage) ? (
          <ErrorNotice
            errorMessage={errorMessage || 'ClickHouse server is unreachable.'}
            onRetry={fetchAllData}
            isRetrying={isRefreshing}
          />
        ) : (
          <>
            {/* Anomaly Detection Banner */}
            <AnomalyBanner
              anomalies={anomalies}
              incident={incident}
              onInvestigate={handleInvestigate}
              onResolve={handleToggleIncident}
            />

            {/* Top-Level KPI Strip */}
            <KpiStrip kpis={kpis} />

            {/* Row 1: Real-Time Charts (Velocity & Success/Latency Trend) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <VelocityChart timeseries={timeseries} />
              <SuccessLatencyChart timeseries={timeseries} />
            </div>

            {/* Row 2: Slice Distributions (Gateways, Rails, Response Codes) */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <GatewayHealthChart
                gateways={gateways}
                onSelectGateway={(gw) => {
                  setInvestigatingSlice((prev) => ({ ...prev, gateway: gw }));
                  const el = document.getElementById('drill-down-section');
                  if (el) el.scrollIntoView({ behavior: 'smooth' });
                }}
              />
              <RailDistributionChart
                rails={rails}
                onSelectRail={(rail) => {
                  setInvestigatingSlice((prev) => ({ ...prev, rail }));
                  const el = document.getElementById('drill-down-section');
                  if (el) el.scrollIntoView({ behavior: 'smooth' });
                }}
              />
              <ResponseCodesChart responseCodes={responseCodes} />
            </div>

            {/* Row 3: Interactive Drill-Down Investigation */}
            <div id="drill-down-section">
              <DrillDownExplorer
                initialSlice={investigatingSlice}
                onClearSlice={() => setInvestigatingSlice(null)}
              />
            </div>

            {/* Row 4: Real-Time Transaction Stream */}
            <LiveTransactionsTable transactions={transactions} />
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white px-6 py-4 text-center text-xs text-gray-500 font-mono flex flex-col sm:flex-row items-center justify-between gap-2 max-w-[1700px] w-full mx-auto">
        <div>
          <span>Architecture: </span>
          <span className="text-gray-600">Kafka Topic → ClickHouse MergeTree → FastAPI → React (Chart.js)</span>
        </div>
        <div className="flex items-center space-x-4">
          <span>ClickHouse DB: <strong className="text-blue-600">bank_demo</strong></span>
          <span>•</span>
          <span>Engine: <strong className="text-purple-600">AggregatingMergeTree (1m)</strong></span>
        </div>
      </footer>

      {/* AI Analyst Floating Button */}
      <AIAnalystButton />
    </div>
  );
};

export default App;
