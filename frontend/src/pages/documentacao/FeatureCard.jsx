export default function FeatureCard({ icon, title, desc }) {
  return (
    <div className="doc-feature-card">
      <div className="doc-feature-icon">{icon}</div>
      <div>
        <div className="doc-feature-title">{title}</div>
        {desc && <div className="doc-feature-desc">{desc}</div>}
      </div>
    </div>
  );
}
