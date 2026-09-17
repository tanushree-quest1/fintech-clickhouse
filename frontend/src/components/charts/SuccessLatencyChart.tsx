import React from 'react';
import './chartSetup';
import { Line } from 'react-chartjs-2';
import { TimeseriesPoint } from '../../types';

interface SuccessLatencyChartProps {
  timeseries: TimeseriesPoint[];
}

export const SuccessLatencyChart: React.FC<SuccessLatencyChartProps> = ({ timeseries }) => {
  const labels = timeseries.map((pt) => pt.minute);
  const successRates = timeseries.map((pt) => pt.success_rate);
  const latencies = timeseries.map((pt) => pt.avg_latency);

  const minSuccess = Math.max(80, Math.floor(Math.min(...successRates, 98) - 2));

  const data = {
    labels,
    datasets: [
      {
        label: 'Success Rate (%)',
        data: successRates,
        borderColor: '#10B981',
        backgroundColor: 'rgba(16, 185, 129, 0.08)',
        borderWidth: 2.5,
        tension: 0.35,
        fill: true,
        pointRadius: 2,
        pointHoverRadius: 5,
        yAxisID: 'ySuccess',
      },
      {
        label: 'Avg Latency (ms)',
        data: latencies,
        borderColor: '#F59E0B',
        backgroundColor: 'transparent',
        borderWidth: 2,
        borderDash: [4, 4],
        tension: 0.3,
        pointRadius: 2,
        pointHoverRadius: 5,
        yAxisID: 'yLatency',
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
      ySuccess: {
        type: 'linear' as const,
        display: true,
        position: 'left' as const,
        min: minSuccess,
        max: 100,
        grid: { color: '#e5e7eb' },
        ticks: {
          color: '#10b981',
          font: { size: 10 },
          callback: (value: any) => `${value}%`,
        },
        title: {
          display: true,
          text: 'Success Rate (%)',
          color: '#10b981',
          font: { size: 10 },
        },
      },
      yLatency: {
        type: 'linear' as const,
        display: true,
        position: 'right' as const,
        grid: { drawOnChartArea: false },
        ticks: {
          color: '#f59e0b',
          font: { size: 10 },
          callback: (value: any) => `${Math.round(value)}ms`,
        },
        title: {
          display: true,
          text: 'Latency (ms)',
          color: '#f59e0b',
          font: { size: 10 },
        },
      },
    },
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm flex flex-col h-[320px]">
      <div className="mb-3">
        <h3 className="text-sm font-bold text-gray-900 font-mono">
          AUTHORIZATION SUCCESS RATE & LATENCY TREND
        </h3>
        <p className="text-xs text-gray-500">Correlation of system degradation & SLA breaches</p>
      </div>
      <div className="flex-1 min-h-0 relative">
        <Line data={data} options={options} />
      </div>
    </div>
  );
};
