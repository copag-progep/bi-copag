import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import ChartPanel from "../components/ChartPanel";


function AxisTick({ x, y, payload, formatter }) {
  const fullLabel = String(payload?.value ?? "");
  const displayLabel = formatter ? formatter(fullLabel) : fullLabel;

  return (
    <g transform={`translate(${x},${y})`}>
      <title>{fullLabel}</title>
      <text x={0} y={0} dy={16} textAnchor="middle" fill="#667675" fontSize={12}>
        {displayLabel}
      </text>
    </g>
  );
}


export default function BarChartCard({ title, subtitle, data, color = "#0c7a6c", tickFormatter }) {
  return (
    <ChartPanel title={title} subtitle={subtitle}>
      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={false}
              tick={<AxisTick formatter={tickFormatter} />}
            />
            <YAxis tickLine={false} axisLine={false} />
            <Tooltip />
            <Bar dataKey="value" fill={color} radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartPanel>
  );
}
