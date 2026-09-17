import React from 'react';
import { AnomalyItem, IncidentStatus } from '../types';

interface AnomalyBannerProps {
  anomalies: AnomalyItem[];
  incident: IncidentStatus | null;
  onInvestigate: (anomaly: AnomalyItem) => void;
  onResolve: () => void;
}

export const AnomalyBanner: React.FC<AnomalyBannerProps> = ({
  anomalies,
  incident,
  onInvestigate,
  onResolve,
}) => {
  const topAnomaly = anomalies && anomalies.length > 0 ? anomalies[0] : null;

  if (!topAnomaly && !incident?.active) {
    return (
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <div className="text-sm font-semibold text-green-700 font-mono">
          ALL SYSTEMS HEALTHY — NO STATISTICAL ANOMALIES DETECTED
        </div>
        <div className="text-xs text-gray-600 mt-1">
          ClickHouse continuous slice baseline analysis operating normally across all rails and gateways.
        </div>
      </div>
    );
  }

  const slice = topAnomaly || {
    payment_rail: incident?.target.rail || 'Card',
    region: incident?.target.region || 'Georgia',
    merchant_category: incident?.target.category || 'E-commerce',
    gateway: incident?.target.gateway || 'Gateway Y',
    current_failure_rate_pct: incident?.current_failure_rate || 11.8,
    baseline_failure_rate_pct: 1.9,
    times_above_baseline: Math.round(((incident?.current_failure_rate || 11.8) / 1.9) * 10) / 10,
  };

  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Left summary */}
        <div>
          <div className="text-sm font-semibold text-red-700 font-mono">
            CRITICAL ANOMALY DETECTED
          </div>
          <div className="text-xs text-red-600 font-mono mt-1">
            Flagged by ClickHouse 15m Slice Engine
          </div>

          <div className="mt-2 text-sm text-gray-700">
            Deviating slice:{' '}
            <span className="font-bold text-gray-900 font-mono">
              {slice.region} • {slice.payment_rail} • {slice.merchant_category} • {slice.gateway}
            </span>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
            <span className="text-red-700 font-medium">
              Failure Rate: <strong className="text-red-600 font-mono text-sm">{slice.current_failure_rate_pct}%</strong>
            </span>
            <span className="text-gray-600 font-mono">
              (Baseline: {slice.baseline_failure_rate_pct}%)
            </span>
            <span className="text-red-700 font-mono font-bold">
              {slice.times_above_baseline}x above historical baseline
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-3 self-end lg:self-center">
          {topAnomaly && (
            <button
              onClick={() => onInvestigate(topAnomaly)}
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold font-mono transition-colors"
            >
              INVESTIGATE
            </button>
          )}

          {incident?.active && (
            <button
              onClick={onResolve}
              className="px-4 py-2 rounded-lg bg-gray-200 hover:bg-gray-300 border border-gray-300 text-gray-700 text-xs font-bold font-mono transition-colors"
            >
              RESOLVE
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
