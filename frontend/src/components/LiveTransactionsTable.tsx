import React from 'react';
import { TransactionItem } from '../types';

interface LiveTransactionsTableProps {
  transactions: TransactionItem[];
}

export const LiveTransactionsTable: React.FC<LiveTransactionsTableProps> = ({ transactions }) => {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm flex flex-col">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-200">
        <div className="flex items-center space-x-2">
          <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
          <div>
            <h3 className="text-sm font-bold text-gray-900 font-mono">
              REAL-TIME TRANSACTION STREAM
            </h3>
            <p className="text-xs text-gray-500">
              Live ClickHouse ingested feed (Kafka → transactions table)
            </p>
          </div>
        </div>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="text-gray-500 font-mono border-b border-gray-200 text-[11px]">
              <th className="pb-2 font-medium">TIME</th>
              <th className="pb-2 font-medium">TXN ID</th>
              <th className="pb-2 font-medium">BANK</th>
              <th className="pb-2 font-medium">RAIL</th>
              <th className="pb-2 font-medium">GATEWAY</th>
              <th className="pb-2 font-medium text-right">AMOUNT</th>
              <th className="pb-2 font-medium text-center">STATUS</th>
              <th className="pb-2 font-medium text-center">CODE</th>
              <th className="pb-2 font-medium text-right">LATENCY</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 font-mono">
            {transactions.map((t, idx) => {
              const isSuccess = t.authorization_status === 'SUCCESS';
              const isIncident = t.is_synthetic_incident === 1;

              return (
                <tr
                  key={`${t.transaction_id}-${idx}`}
                  className={`hover:bg-gray-50 transition-colors ${
                    isIncident ? 'bg-red-50' : ''
                  }`}
                >
                  <td className="py-2.5 text-gray-500 whitespace-nowrap">{t.time_str}</td>
                  <td className="py-2.5 text-blue-600 font-semibold">{t.transaction_id}</td>
                  <td className="py-2.5 text-gray-700">{t.bank}</td>
                  <td className="py-2.5">
                    <span className="text-gray-700 text-[10px]">
                      {t.payment_rail}
                    </span>
                  </td>
                  <td className="py-2.5">
                    <span className={`font-semibold ${t.gateway === 'Gateway Y' ? 'text-amber-600' : 'text-gray-700'}`}>
                      {t.gateway}
                    </span>
                  </td>
                  <td className="py-2.5 text-right font-semibold text-gray-900">
                    {`$${Number(t.amount).toLocaleString('en-US', {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}`}
                  </td>
                  <td className="py-2.5 text-center">
                    <span
                      className={`text-[10px] font-bold ${
                        isSuccess
                          ? 'text-green-700'
                          : 'text-red-700'
                      }`}
                    >
                      {t.authorization_status}
                    </span>
                  </td>
                  <td className="py-2.5 text-center text-gray-500">
                    <span className={t.response_code !== '00' ? 'text-red-600 font-bold' : ''}>
                      {t.response_code}
                    </span>
                  </td>
                  <td className="py-2.5 text-right text-gray-700">
                    <span className={t.latency_ms > 400 ? 'text-amber-600 font-bold' : ''}>
                      {Math.round(Number(t.latency_ms))} ms
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
