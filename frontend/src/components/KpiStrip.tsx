import React from 'react';
import { KpiData } from '../types';

interface KpiStripProps {
  kpis: KpiData | null;
}

export const KpiStrip: React.FC<KpiStripProps> = ({ kpis }) => {
  if (!kpis) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-28 bg-gray-100 border border-gray-200 rounded-lg" />
        ))}
      </div>
    );
  }

  // Format USD nicely for a US banking demo.
  const formatUSD = (amt: number) => {
    if (amt >= 1000000000) {
      return `$${(amt / 1000000000).toFixed(2)}B`;
    }
    if (amt >= 1000000) {
      return `$${(amt / 1000000).toFixed(2)}M`;
    }
    if (amt >= 1000) {
      return `$${(amt / 1000).toFixed(2)}K`;
    }
    return `$${amt.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
  };

  const formatCount = (val: number) => {
    if (val >= 1000000) {
      return `${(val / 1000000).toFixed(2)}M`;
    }
    if (val >= 1000) {
      return `${(val / 1000).toFixed(1)}K`;
    }
    return val.toLocaleString();
  };

  const isSuccessHealthy = kpis.success_rate_pct >= 98.0;
  const isLatencyHealthy = kpis.avg_latency_ms < 300;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Transaction Volume & Count */}
      <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm relative overflow-hidden group hover:border-gray-300 transition-all">
        <div className="flex items-center justify-between text-xs text-gray-500 mb-1 font-medium">
          <span>TRANSACTIONS (15M)</span>
        </div>
        <div className="flex items-baseline space-x-2 mt-1">
          <span className="text-2xl font-bold tracking-tight text-gray-900 font-['JetBrains_Mono',monospace]">
            {formatUSD(kpis.total_volume)}
          </span>
          <span className="text-xs text-gray-500 font-mono">
            ({formatCount(kpis.total_txns)} txns)
          </span>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-gray-500 border-t border-gray-200 pt-2">
          <span>Throughput:</span>
          <span className="font-mono text-gray-700">~{Math.round(kpis.total_txns / 900)} TPS</span>
        </div>
      </div>

      {/* 2. Success Rate */}
      <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm relative overflow-hidden group hover:border-gray-300 transition-all">
        <div className="flex items-center justify-between text-xs text-gray-500 mb-1 font-medium">
          <span>SUCCESS RATE</span>
        </div>
        <div className="flex items-baseline space-x-2 mt-1">
          <span className={`text-2xl font-bold tracking-tight font-['JetBrains_Mono',monospace] ${
            isSuccessHealthy ? 'text-green-600' : 'text-red-600'
          }`}>
            {kpis.success_rate_pct.toFixed(2)}%
          </span>
          <span className="text-xs text-gray-500 font-mono">
            Target &gt;98%
          </span>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-gray-500 border-t border-gray-200 pt-2">
          <span>Failed Txns:</span>
          <span className="font-mono text-red-600">
            {Math.round(kpis.total_txns * (1 - kpis.success_rate_pct / 100)).toLocaleString()}
          </span>
        </div>
      </div>

      {/* 3. Average Latency */}
      <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm relative overflow-hidden group hover:border-gray-300 transition-all">
        <div className="flex items-center justify-between text-xs text-gray-500 mb-1 font-medium">
          <span>AVG LATENCY</span>
        </div>
        <div className="flex items-baseline space-x-2 mt-1">
          <span className={`text-2xl font-bold tracking-tight font-['JetBrains_Mono',monospace] ${
            isLatencyHealthy ? 'text-gray-900' : 'text-amber-600'
          }`}>
            {kpis.avg_latency_ms.toFixed(0)} ms
          </span>
          <span className="text-xs text-gray-500 font-mono">
            p95: ~{(kpis.avg_latency_ms * 1.8).toFixed(0)}ms
          </span>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-gray-500 border-t border-gray-200 pt-2">
          <span>SLA Benchmark:</span>
          <span className="font-mono text-gray-700">&lt; 350 ms</span>
        </div>
      </div>

      {/* 4. Active Merchants & Fraud Risk */}
      <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm relative overflow-hidden group hover:border-gray-300 transition-all">
        <div className="flex items-center justify-between text-xs text-gray-500 mb-1 font-medium">
          <span>NETWORK FOOTPRINT</span>
        </div>
        <div className="flex items-baseline space-x-2 mt-1">
          <span className="text-2xl font-bold tracking-tight text-gray-900 font-['JetBrains_Mono',monospace]">
            {kpis.active_merchants.toLocaleString()}
          </span>
          <span className="text-xs text-gray-500 font-mono">
            active
          </span>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs border-t border-gray-200 pt-2">
          <span className="text-gray-500">
            Fraud Flags:
          </span>
          <span className="font-mono text-amber-600 font-medium">
            {kpis.fraud_risk_count.toLocaleString()}
          </span>
        </div>
      </div>
    </div>
  );
};
