import React, { useState, useEffect } from 'react';
import { DrilldownData } from '../types';

const API_BASE = 'http://127.0.0.1:8000';

interface DrillDownProps {
  initialSlice?: {
    rail?: string;
    region?: string;
    category?: string;
    gateway?: string;
  } | null;
  onClearSlice?: () => void;
}

export const DrillDownExplorer: React.FC<DrillDownProps> = ({
  initialSlice,
  onClearSlice,
}) => {
  const [selectedBank, setSelectedBank] = useState<string>('All');
  const [selectedRail, setSelectedRail] = useState<string>('All');
  const [selectedRegion, setSelectedRegion] = useState<string>('All');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [selectedGateway, setSelectedGateway] = useState<string>('All');
  const [drilldown, setDrilldown] = useState<DrilldownData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // If parent requests investigation of an anomaly slice, apply it
  useEffect(() => {
    if (initialSlice) {
      if (initialSlice.rail) setSelectedRail(initialSlice.rail);
      if (initialSlice.region) setSelectedRegion(initialSlice.region);
      if (initialSlice.category) setSelectedCategory(initialSlice.category);
      if (initialSlice.gateway) setSelectedGateway(initialSlice.gateway);
    }
  }, [initialSlice]);

  useEffect(() => {
    const params = new URLSearchParams({
      bank: selectedBank,
      rail: selectedRail,
      region: selectedRegion,
      category: selectedCategory,
      gateway: selectedGateway,
    });

    let cancelled = false;
    setIsLoading(true);
    fetch(`${API_BASE}/api/drilldown?${params.toString()}`)
      .then((response) => {
        if (!response.ok) throw new Error('Unable to load drilldown data');
        return response.json() as Promise<DrilldownData>;
      })
      .then((data) => {
        if (!cancelled) {
          setDrilldown(data);
          setError(null);
        }
      })
      .catch((requestError: Error) => {
        if (!cancelled) setError(requestError.message);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedBank, selectedRail, selectedRegion, selectedCategory, selectedGateway]);

  const banks = ['All', 'Chase', 'Bank of America', 'Wells Fargo', 'Citibank', 'US Bank'];
  const rails = ['All', 'Card', 'ACH', 'Wire', 'Zelle', 'PayPal'];
  const regions = ['All', 'California', 'Texas', 'New York', 'Florida', 'Illinois', 'Pennsylvania', 'Ohio'];
  const categories = ['All', 'E-commerce', 'Travel', 'Food Delivery', 'Utilities', 'Groceries', 'Entertainment'];
  const gateways = ['All', 'Gateway A', 'Gateway B', 'Gateway X', 'Gateway Y', 'Gateway Z'];

  const resetAll = () => {
    setSelectedBank('All');
    setSelectedRail('All');
    setSelectedRegion('All');
    setSelectedCategory('All');
    setSelectedGateway('All');
    if (onClearSlice) onClearSlice();
  };

  const failureRate = drilldown?.failure_rate_pct ?? 0;
  const isAnomalySlice = failureRate > 2.1;
  const status = !drilldown || drilldown.total === 0
    ? 'NO DATA'
    : isAnomalySlice ? 'ISSUE' : 'OK';
  const formatVolume = (amount: number) => `$${amount.toLocaleString('en-US', {
    maximumFractionDigits: 0,
  })}`;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-gray-200">
        <div>
          <h3 className="text-sm font-bold text-gray-900 font-mono">
            DRILL DOWN BY DIMENSION
          </h3>
          <p className="text-xs text-gray-500">
            Select filters to analyze specific transaction segments
          </p>
        </div>

        <button
          onClick={resetAll}
          className="px-2.5 py-1 text-xs font-mono text-gray-600 hover:text-gray-900 bg-gray-100 border border-gray-200 rounded-lg hover:border-gray-300 transition-colors self-start sm:self-auto"
        >
          Reset All
        </button>
      </div>

      {/* Filter Selector Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-4">
        {/* Bank */}
        <div>
          <label className="text-[11px] font-mono text-gray-500 mb-1">
            Bank
          </label>
          <select
            value={selectedBank}
            onChange={(e) => setSelectedBank(e.target.value)}
            className="w-full bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-700 focus:outline-none focus:border-blue-500 font-mono"
          >
            {banks.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
        </div>

        {/* Payment Rail */}
        <div>
          <label className="text-[11px] font-mono text-gray-500 mb-1">
            Payment Rail
          </label>
          <select
            value={selectedRail}
            onChange={(e) => setSelectedRail(e.target.value)}
            className="w-full bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-700 focus:outline-none focus:border-blue-500 font-mono"
          >
            {rails.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>

        {/* Region */}
        <div>
          <label className="text-[11px] font-mono text-gray-500 mb-1">
            Region
          </label>
          <select
            value={selectedRegion}
            onChange={(e) => setSelectedRegion(e.target.value)}
            className="w-full bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-700 focus:outline-none focus:border-blue-500 font-mono"
          >
            {regions.map((rg) => (
              <option key={rg} value={rg}>{rg}</option>
            ))}
          </select>
        </div>

        {/* Merchant Category */}
        <div>
          <label className="text-[11px] font-mono text-gray-500 mb-1">
            Category
          </label>
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="w-full bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-700 focus:outline-none focus:border-blue-500 font-mono"
          >
            {categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        {/* Gateway */}
        <div>
          <label className="text-[11px] font-mono text-gray-500 mb-1">
            Gateway
          </label>
          <select
            value={selectedGateway}
            onChange={(e) => setSelectedGateway(e.target.value)}
            className="w-full bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-700 focus:outline-none focus:border-blue-500 font-mono"
          >
            {gateways.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Slice Stats Bar */}
      <div className={`p-4 rounded-lg border flex flex-col md:flex-row md:items-center justify-between gap-4 transition-colors ${
        isAnomalySlice 
          ? 'bg-red-50 border-red-200 text-red-900' 
          : 'bg-gray-50 border-gray-200 text-gray-700'
      }`}>
        <div className="flex items-center space-x-3">
          <div>
            <div className="text-xs font-mono uppercase tracking-wider text-gray-500">
              Current Selection
            </div>
            <div className="text-sm font-semibold font-mono text-gray-900 mt-0.5">
              {selectedBank} / {selectedRail} / {selectedRegion} / {selectedCategory} / {selectedGateway}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-6 text-xs font-mono">
          <div>
            <span className="text-gray-500 block text-[10px]">FAILURE RATE</span>
            <span className={`text-base font-bold ${isAnomalySlice ? 'text-red-600' : 'text-green-600'}`}>
              {isLoading ? '...' : `${failureRate.toFixed(2)}%`}
            </span>
          </div>

          <div>
            <span className="text-gray-500 block text-[10px]">AVG LATENCY</span>
            <span className={`text-base font-bold ${isAnomalySlice ? 'text-red-600' : 'text-blue-600'}`}>
              {isLoading ? '...' : `${drilldown?.avg_latency_ms.toFixed(0) ?? '0'} ms`}
            </span>
          </div>

          <div>
            <span className="text-gray-500 block text-[10px]">STATUS</span>
            <span className={`text-[11px] font-bold ${isAnomalySlice ? 'text-red-600' : 'text-green-600'}`}>
              {isLoading ? 'LOADING' : status}
            </span>
          </div>
        </div>
      </div>

      {/* Top affected merchants in this slice */}
      <div className="mt-4 pt-3 border-t border-gray-200">
        <div className="text-xs font-mono text-gray-500 mb-2">
          TOP MERCHANTS BY FAILURE COUNT
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-xs">
          {error ? (
            <div className="text-xs text-red-600">{error}</div>
          ) : drilldown?.merchants.length ? (
            drilldown.merchants.map((merchant) => (
              <div key={merchant.merchant_name} className="bg-gray-50 border border-gray-200 rounded-lg p-2.5 flex items-center justify-between">
                <div>
                  <div className="font-semibold text-gray-700">{merchant.merchant_name}</div>
                  <div className="text-[10px] text-gray-500 font-mono">{formatVolume(merchant.volume)}</div>
                </div>
                <div className="text-right font-mono">
                  <span className={`font-bold ${isAnomalySlice ? 'text-red-600' : 'text-gray-600'}`}>
                    {merchant.failed.toLocaleString()}
                  </span>
                  <div className="text-[10px] text-gray-500">failed</div>
                </div>
              </div>
            ))
          ) : (
            <div className="text-xs text-gray-500">No failed transactions in this slice.</div>
          )}
        </div>
      </div>
    </div>
  );
};
