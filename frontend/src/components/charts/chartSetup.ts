import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

// Global Chart.js styling defaults for Fintech Dark Theme
ChartJS.defaults.color = '#9CA3AF';
ChartJS.defaults.borderColor = '#1F2937';
ChartJS.defaults.font.family = "'Plus Jakarta Sans', sans-serif";

export default ChartJS;
