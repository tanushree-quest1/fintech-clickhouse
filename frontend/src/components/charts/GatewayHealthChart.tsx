import React from 'react';
import './chartSetup';
import { Bar } from 'react-chartjs-2';
import { GatewayMetric } from '../../types';

interface GatewayHealthChartProps {
  gateways: GatewayMetric[];
  onSelectGateway?: (gw: string) => void;
}

export const GatewayHealthChart: React.FC<GatewayHealthChartProps> = ({ 
  gateways,
  onSelectGateway 
}) => {
  const labels = gateways.map((g) => g.gateway);
  const failureRates = gateways.map((g) => g.failure_rate_pct);
  const latencies = gateways.map((g) => g.avg_latency_ms);

  const backgroundColors = gateways.map((g) => {
    if (g.failure_rate_pct > 6.0) return 'rgba(239, 68, 68, 0.85)'; // Red
    if (g.failure_rate_pct > 3.0) return 'rgba(245, 158, 11, 0.85)'; // Amber
    return 'rgba(59, 130, 246, 0.75)'; // Blue
  });

  const borderColors = gateways.map((g) => {
    if (g.failure_rate_pct > 6.0) return '#EF4444';
    if (g.failure_rate_pct > 3.0) return '#F59E0B';
    return '#3B82F6';
  });

  const data = {
    labels,
    datasets: [
      {
        label: 'Failure Rate (%)',
        data: failureRates,
        backgroundColor: backgroundColors,
        borderColor: borderColors,
        borderWidth: 1.5,
        borderRadius: 6,
        yAxisID: 'yFailRate',
      },
    ],
  };

  const options: any = {
    responsive: true,
    maintainAspectRatio: false,
    onClick: (_: any, elements: any[]) => {
      if (elements.length > 0 && onSelectGateway) {
        const index = elements[0].index;
        onSelectGateway(labels[index]);
      }
    },
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: '#ffffff',
        titleColor: '#111827',
        bodyColor: '#374151',
        borderColor: '#d1d5db',
        borderWidth: 1,
        padding: 10,
        callbacks: {
          afterLabel: (ctx: any) => {
            const gw = gateways[ctx.dataIndex];
            return `Avg Latency: ${gw.avg_latency_ms}ms\nTotal Volume: ${gw.total.toLocaleString()}`;
          }
        }
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: '#374151', font: { size: 11, weight: 'bold' } },
      },
      yFailRate: {
        type: 'linear' as const,
        grid: { color: '#e5e7eb' },
        ticks: {
          color: '#ef4444',
          font: { size: 10 },
          callback: (val: any) => `${val}%`,
        },
        title: {
          display: true,
          text: 'Failure Rate (%)',
          color: '#6b7280',
          font: { size: 10 },
        },
      },
    },
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm flex flex-col h-[300px]">
      <div className="mb-3">
        <h3 className="text-sm font-bold text-gray-900 font-mono">
          GATEWAY HEALTH & FAILURE PROFILE
        </h3>
        <p className="text-xs text-gray-500">Click a bar to isolate and drill into gateway</p>
      </div>
      <div className="flex-1 min-h-0 relative">
        <Bar data={data} options={options} />
      </div>
    </div>
  );
};
