import React from 'react';
import { IncidentStatus } from '../types';

interface HeaderProps {
  chConnected: boolean;
  wsConnected: boolean;
  incident: IncidentStatus | null;
  refreshInterval: number;
  onIntervalChange: (sec: number) => void;
  onManualRefresh: () => void;
  onToggleIncident: () => void;
  isRefreshing: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  chConnected,
  wsConnected,
  incident,
  refreshInterval,
  onIntervalChange,
  onManualRefresh,
  onToggleIncident,
  isRefreshing,
}) => {
  const isIncidentActive = incident?.active;

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-50 px-6 py-4 shadow-sm">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        {/* Title & Brand */}
        <div className="flex items-center space-x-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-gray-900 font-['JetBrains_Mono',monospace]">
              BANKING CONTROL TOWER
            </h1>
          </div>
        </div>

        {/* Live Status Indicators */}
        <div className="flex flex-wrap items-center gap-3">
          {/* ClickHouse Status */}
          <div className={`flex items-center space-x-2 text-xs font-mono ${
            chConnected 
              ? 'text-green-700'
              : 'text-red-700'
          }`}>
            <span>ClickHouse:</span>
            <span className="font-semibold">{chConnected ? 'Connected' : 'Disconnected'}</span>
          </div>

          {/* WebSocket Status */}
          <div className={`flex items-center space-x-2 text-xs font-mono ${
            wsConnected 
              ? 'text-blue-700'
              : 'text-gray-600'
          }`}>
            <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-gray-400'}`} />
            <span>{wsConnected ? 'LIVE' : 'POLLING'}</span>
          </div>

          {/* Refresh Selector */}
          <div className="flex items-center space-x-1 text-xs">
            {[1, 2, 5].map((sec) => (
              <button
                key={sec}
                onClick={() => onIntervalChange(sec)}
                className={`px-2 py-0.5 rounded font-mono transition-colors ${
                  refreshInterval === sec 
                    ? 'bg-blue-600 text-white font-medium' 
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                {sec}s
              </button>
            ))}
            <button
              onClick={() => onIntervalChange(0)}
              className={`px-2 py-0.5 rounded font-mono transition-colors ${
                refreshInterval === 0 
                  ? 'bg-blue-600 text-white font-medium' 
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Pause
            </button>
          </div>

          {/* Manual Refresh Button */}
          <button
            onClick={onManualRefresh}
            disabled={isRefreshing}
            className="px-2 py-0.5 rounded bg-gray-100 text-gray-600 hover:bg-gray-200 hover:text-gray-900 transition-colors disabled:opacity-50 text-xs"
          >
            {isRefreshing ? '⟳' : '↻'}
          </button>

          {/* Fault Injector Toggle Button */}
          <button
            onClick={onToggleIncident}
            className={`px-3 py-0.5 rounded text-xs font-semibold transition-colors ${
              isIncidentActive
                ? 'bg-red-500 hover:bg-red-600 text-white'
                : 'bg-gray-100 hover:bg-amber-50 text-amber-700'
            }`}
          >
            {isIncidentActive ? 'RESOLVE' : 'INJECT'}
          </button>
        </div>
      </div>
    </header>
  );
};
