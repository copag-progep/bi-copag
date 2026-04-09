import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import ChartPanel from "../components/ChartPanel";


const palette = ["#0c7a6c", "#0f5f73", "#c2603b", "#d39c24", "#5b4f9c", "#8d2f51", "#1b8f52", "#3b6bd4"];


function pivotSeries(data, xKey, seriesKey, valueKey) {
  if (!seriesKey) {
    return data;
  }

  const bucket = new Map();
  for (const item of data) {
    const axisValue = item[xKey];
    if (!bucket.has(axisValue)) {
      bucket.set(axisValue, { [xKey]: axisValue });
    }
    bucket.get(axisValue)[item[seriesKey]] = item[valueKey];
  }
  return Array.from(bucket.values());
}


export default function LineChartCard({ title, subtitle, data, xKey, valueKey, seriesKey, formatSeriesName }) {
  const chartData = pivotSeries(data, xKey, seriesKey, valueKey);
  const series = seriesKey ? [...new Set(data.map((item) => item[seriesKey]))] : [valueKey];

  function formatLegendValue(value) {
    if (!seriesKey) {
      return value;
    }

    return (
      <span className="chart-legend-label" title={value}>
        {seriesKey && typeof formatSeriesName === "function" ? formatSeriesName(value) : value}
      </span>
    );
  }

  return (
    <ChartPanel title={title} subtitle={subtitle}>
      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey={xKey} tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} />
            <Tooltip />
            {seriesKey ? <Legend formatter={formatLegendValue} /> : null}
            {series.map((seriesName, index) => (
              <Line
                key={seriesName}
                type="monotone"
                dataKey={seriesName}
                stroke={palette[index % palette.length]}
                strokeWidth={2.5}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartPanel>
  );
}
