import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import ChartPanel from "../components/ChartPanel";


const palette = ["#0c7a6c", "#0f5f73", "#c2603b", "#d39c24", "#5b4f9c", "#8d2f51", "#1b8f52", "#3b6bd4"];


export default function PieChartCard({ title, subtitle, data }) {
  return (
    <ChartPanel title={title} subtitle={subtitle}>
      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={320}>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="label" outerRadius={110} innerRadius={55}>
              {data.map((entry, index) => (
                <Cell key={entry.label} fill={palette[index % palette.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </ChartPanel>
  );
}
