import React from 'react';
import './chartSetup';
import { Chart } from 'react-chartjs-2';
import { TimeseriesPoint } from '../../types';

interface VelocityChartProps {
  timeseries: TimeseriesPoint[];
}

export const VelocityChart: React.FC<VelocityChartProps> = ({ timeseries }) => {
  const labels = timeseries.map((pt) => pt.minute);
  const totals = timeseries.map((pt) => pt.total);
  const failed = timeseries.map((pt) => pt.failed);
  const failureRates = timeseries.map((pt) => (pt.total > 0 ? (pt.failed / pt.total) * 100 : 0));
  const minFailureRate = failureRates.length ? Math.min(...failureRates) : 0;
  const maxFailureRate = failureRates.length ? Math.max(...failureRates) : 0;

  const data = {
    labels,
    datasets: [
      {
        label: 'Total Transactions',
        data: totals,
        borderColor: '#3B82F6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderWidth: 2,
        tension: 0.35,
        fill: true,
        pointRadius: 2,
        pointHoverRadius: 5,
        yAxisID: 'y',
      },
      {
        label: 'Failed Transactions',
        type: 'bar' as const,
        data: failed,
        borderColor: '#EF4444',
        backgroundColor: 'rgba(239, 68, 68, 0.7)',
        borderWidth: 1,
        borderRadius: 3,
        yAxisID: 'y',
      },
    ],
  };

  const options: any = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 400,
    },
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          color: '#374151',
          boxWidth: 12,
          usePointStyle: true,
          font: { size: 11 },
        },
      },
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
        type: 'linear' as const,
        display: true,
        position: 'left' as const,
        beginAtZero: true,
        grid: { color: '#e5e7eb' },
        ticks: {
          color: '#6b7280',
          font: { size: 10 },
          callback: (value: any) => `${(value / 1000).toFixed(0)}k`,
        },
        title: {
          display: true,
          text: 'Transactions',
          color: '#6b7280',
          font: { size: 10 },
        },
      },
    },
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm flex flex-col h-[320px]">
      <div className="mb-3">
        <h3 className="text-sm font-bold text-gray-900 font-mono">
          TRANSACTION VELOCITY & FAILURE VOLUME
        </h3>
        <p className="text-xs text-gray-500">
          Real-time aggregate per minute from ClickHouse - Failure rate {minFailureRate.toFixed(1)} to {maxFailureRate.toFixed(1)}%
        </p>
      </div>
      <div className="flex-1 min-h-0 relative">
        <Chart type="line" data={data as any} options={options} />
      </div>
    </div>
  );
};
