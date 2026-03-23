export default function ChartPanel({ title, subtitle, children }) {
  return (
    <article className="panel chart-panel">
      <div className="panel-header">
        <div>
          <h3>{title}</h3>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </div>
      <div className="panel-body">{children}</div>
    </article>
  );
}
