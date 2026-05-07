export default function Callout({ icon = "💡", children }) {
  return (
    <div className="doc-callout">
      <span className="doc-callout-icon">{icon}</span>
      <div className="doc-callout-body">{children}</div>
    </div>
  );
}
