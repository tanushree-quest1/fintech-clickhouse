import React from 'react';
import './chartSetup';
import { Bar } from 'react-chartjs-2';
import { ResponseCodeMetric } from '../../types';

interface ResponseCodesChartProps {
  responseCodes: ResponseCodeMetric[];
}

export const ResponseCodesChart: React.FC<ResponseCodesChartProps> = ({ responseCodes }) => {
  const codeLabels: Record<string, string> = {
    '91': '91 - System Error',
    '96': '96 - Gateway Timeout',
    '51': '51 - Insufficient Funds',
    '34': '34 - Suspected Fraud',
    '05': '05 - Do Not Honor',
    'TO': 'TO - Network Timeout',
    'U30': 'U30 - Gateway Switch Fail',
  };

  const labels = responseCodes.map((c) => codeLabels[c.response_code] || `Code ${c.response_code}`);
  const counts = responseCodes.map((c) => c.count);

  const data = {
    labels,
    datasets: [
      {
        label: 'Failure Count',
        data: counts,
        backgroundColor: (context: any) => {
          const index = context.dataIndex;
          const code = responseCodes[index]?.response_code;
          if (code === '91' || code === '96') {
            return 'rgba(239, 68, 68, 0.85)'; // Red for infrastructure/timeout failure
          }
          return 'rgba(245, 158, 11, 0.75)'; // Amber for other declines
        },
        borderColor: (context: any) => {
          const index = context.dataIndex;
          const code = responseCodes[index]?.response_code;
          if (code === '91' || code === '96') return '#EF4444';
          return '#F59E0B';
        },
        borderWidth: 1.5,
        borderRadius: 4,
      },
    ],
  };

  const options: any = {
    indexAxis: 'y' as const,
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#ffffff',
        titleColor: '#111827',
        bodyColor: '#374151',
        borderColor: '#d1d5db',
        borderWidth: 1,
        padding: 10,
      },
    },
    scales: {
      x: {
        grid: { color: '#e5e7eb' },
        ticks: { color: '#6b7280', font: { size: 10 } },
      },
      y: {
        grid: { display: false },
        ticks: { color: '#374151', font: { size: 11 } },
      },
    },
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm flex flex-col h-[300px]">
      <div className="mb-3">
        <h3 className="text-sm font-bold text-gray-900 font-mono">
          ROOT CAUSE - RESPONSE CODE BREAKDOWN
        </h3>
        <p className="text-xs text-gray-500">Error distributions on authorization rejections</p>
      </div>
      <div className="flex-1 min-h-0 relative">
        <Bar data={data} options={options} />
      </div>
    </div>
  );
};
