import React from 'react';

interface ErrorNoticeProps {
  errorMessage: string;
  onRetry: () => void;
  isRetrying: boolean;
}

export const ErrorNotice: React.FC<ErrorNoticeProps> = ({
  errorMessage,
  onRetry,
  isRetrying,
}) => {
  return (
    <div className="bg-white border-2 border-red-200 rounded-lg p-8 max-w-3xl mx-auto shadow-sm my-8">
      <div className="flex-1">
        <div className="flex items-center space-x-2">
          <span className="bg-red-100 text-red-600 border border-red-200 text-xs font-bold px-2 py-0.5 rounded font-mono uppercase tracking-wider">
            CONNECTION ERROR
          </span>
          <span className="text-xs font-mono text-gray-500">
            ClickHouse / Backend Offline
          </span>
        </div>

        <h2 className="text-lg font-bold text-gray-900 mt-2 font-['JetBrains_Mono',monospace]">
          Unable to Connect to ClickHouse Data Stream
        </h2>

        <p className="text-sm text-gray-600 mt-2">
          {errorMessage || 'ClickHouse server is unreachable at localhost:8123 or backend service is down.'}
        </p>

        {/* Quick Setup Instructions */}
        <div className="mt-5 bg-gray-50 border border-gray-200 rounded-lg p-4 font-mono text-xs text-gray-600 space-y-2">
          <div className="text-gray-500 font-bold mb-2">
            To start the real-time data pipeline:
          </div>
          <div className="flex items-start gap-2">
            <span className="text-blue-600 select-none">1.</span>
            <span>Start ClickHouse and Kafka: <code className="text-amber-700 bg-gray-200 px-1.5 py-0.5 rounded">docker compose up -d</code></span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-blue-600 select-none">2.</span>
            <span>Start FastAPI Backend: <code className="text-amber-700 bg-gray-200 px-1.5 py-0.5 rounded">python -m backend.main</code></span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-blue-600 select-none">3.</span>
            <span>Start Live Kafka Producer: <code className="text-amber-700 bg-gray-200 px-1.5 py-0.5 rounded">python producer.py --rate 2000 --api-port 8001</code></span>
          </div>
        </div>

        {/* Retry Button */}
        <div className="mt-6 flex items-center space-x-3">
          <button
            onClick={onRetry}
            disabled={isRetrying}
            className="flex items-center space-x-2 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold font-mono transition-colors disabled:opacity-50"
          >
            <span>{isRetrying ? '⟳' : '↻'}</span>
            <span>{isRetrying ? 'RETRYING CONNECTION...' : 'RETRY CONNECTION'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
