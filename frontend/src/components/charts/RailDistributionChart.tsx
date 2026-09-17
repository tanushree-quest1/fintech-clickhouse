import React from 'react';
import './chartSetup';
import { Doughnut } from 'react-chartjs-2';
import { RailMetric } from '../../types';

interface RailDistributionChartProps {
  rails: RailMetric[];
  onSelectRail?: (rail: string) => void;
}

export const RailDistributionChart: React.FC<RailDistributionChartProps> = ({
  rails,
  onSelectRail,
}) => {
  const labels = rails.map((r) => r.payment_rail);
  const dataValues = rails.map((r) => r.total);

  const colors = [
    '#3B82F6', // Card (Blue)
    '#8B5CF6', // ACH (Purple)
    '#10B981', // Wire (Emerald)
    '#F59E0B', // Zelle (Amber)
    '#EC4899', // PayPal (Pink)
  ];

  const data = {
    labels,
    datasets: [
      {
        data: dataValues,
        backgroundColor: colors.slice(0, labels.length),
        borderColor: '#ffffff',
        borderWidth: 2,
        hoverOffset: 6,
      },
    ],
  };

  const options: any = {
    responsive: true,
    maintainAspectRatio: false,
    onClick: (_: any, elements: any[]) => {
      if (elements.length > 0 && onSelectRail) {
        const index = elements[0].index;
        onSelectRail(labels[index]);
      }
    },
    plugins: {
      legend: {
        position: 'right' as const,
        labels: {
          color: '#374151',
          boxWidth: 10,
          usePointStyle: true,
          font: { size: 11 },
          generateLabels: (chart: any) => {
            const chartData = chart.data;
            if (chartData.labels.length && chartData.datasets.length) {
              const total = chartData.datasets[0].data.reduce((a: number, b: number) => a + b, 0);
              return chartData.labels.map((label: string, i: number) => {
                const val = chartData.datasets[0].data[i];
                const pct = ((val / (total || 1)) * 100).toFixed(0);
                return {
                  text: `${label} (${pct}%)`,
                  fillStyle: chartData.datasets[0].backgroundColor[i],
                  strokeStyle: '#ffffff',
                  lineWidth: 1,
                  hidden: isNaN(val) || chart.getDatasetMeta(0).data[i].hidden,
                  index: i,
                };
              });
            }
            return [];
          },
        },
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
            const r = rails[ctx.dataIndex];
            return `Success Rate: ${r.success_rate_pct}%\nFailed: ${r.failed.toLocaleString()}`;
          },
        },
      },
    },
    cutout: '68%',
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm flex flex-col h-[300px]">
      <div className="mb-3">
        <h3 className="text-sm font-bold text-gray-900 font-mono">
          PAYMENT RAIL MIX
        </h3>
        <p className="text-xs text-gray-500">Share of volume across payment rails</p>
      </div>
      <div className="flex-1 min-h-0 relative flex items-center justify-center">
        <Doughnut data={data} options={options} />
      </div>
    </div>
  );
};
