import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";


const NUMBER_FORMATTER = new Intl.NumberFormat("pt-BR");


function formatValue(value) {
  if (typeof value !== "number") return value ?? "0";
  return NUMBER_FORMATTER.format(value);
}


export default function SparklineCard({
  label,
  value,
  hint,
  data = [],
  color = "#273168",
  tone = "default",
}) {
  const chartData = data.slice(-7);
  const hasTrend = chartData.length >= 2;
  const gradientId = `spark-${String(label).normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-zA-Z0-9_-]/g, "-")}`;

  return (
    <article className={`spark-card ${tone}`}>
      <div className="spark-card-copy">
        <span>{label}</span>
        <strong>{formatValue(value)}</strong>
        {hint ? <small>{hint}</small> : null}
      </div>

      <div className="spark-card-chart" aria-hidden="true">
        {hasTrend ? (
          <ResponsiveContainer width="100%" height={72}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.28} />
                  <stop offset="100%" stopColor={color} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <Tooltip
                formatter={(tooltipValue) => [formatValue(tooltipValue), label]}
                labelFormatter={(tooltipLabel) => `Data: ${tooltipLabel}`}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={color}
                strokeWidth={2.4}
                fill={`url(#${gradientId})`}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="spark-card-empty">histórico insuficiente</div>
        )}
      </div>
    </article>
  );
}
