export interface KpiData {
  total_txns: number;
  total_volume: number;
  success_rate_pct: number;
  avg_latency_ms: number;
  pct_change: number;
  active_merchants: number;
  fraud_risk_count: number;
}

export interface TimeseriesPoint {
  minute: string;
  total: number;
  failed: number;
  success_rate: number;
  avg_latency: number;
}

export interface GatewayMetric {
  gateway: string;
  total: number;
  failed: number;
  failure_rate_pct: number;
  avg_latency_ms: number;
}

export interface RailMetric {
  payment_rail: string;
  total: number;
  failed: number;
  success_rate_pct: number;
  volume: number;
}

export interface ResponseCodeMetric {
  response_code: string;
  count: number;
  description?: string;
}

export interface AnomalyItem {
  payment_rail: string;
  region: string;
  merchant_category: string;
  gateway: string;
  current_failure_rate_pct: number;
  baseline_failure_rate_pct: number;
  times_above_baseline: number;
}

export interface TransactionItem {
  transaction_id: string;
  time_str: string;
  bank: string;
  payment_rail: string;
  region: string;
  merchant_category: string;
  gateway: string;
  amount: number;
  authorization_status: string;
  response_code: string;
  latency_ms: number;
  is_synthetic_incident?: number;
}

export interface IncidentStatus {
  active: boolean;
  ramp_seconds?: number;
  ramp_fraction: number;
  current_failure_rate: number;
  target: {
    rail: string;
    region: string;
    category: string;
    gateway: string;
    target_failure_rate_pct: number;
    target_latency_ms: number;
  };
}

export interface DrilldownMerchant {
  merchant_name: string;
  total: number;
  failed: number;
  volume: number;
}

export interface DrilldownData {
  total: number;
  failed: number;
  failure_rate_pct: number;
  avg_latency_ms: number;
  merchants: DrilldownMerchant[];
  filters: {
    bank?: string;
    rail?: string;
    region?: string;
    category?: string;
    gateway?: string;
  };
}
