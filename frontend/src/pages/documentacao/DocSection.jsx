export default function DocSection({ id, num, eyebrow, title, children }) {
  return (
    <section id={id} className="doc-section">
      <div className="doc-section-eyebrow">
        <span className="doc-section-num">{num}</span>
        <span className="doc-section-label">{eyebrow}</span>
      </div>
      <h2 className="doc-section-title">{title}</h2>
      <div className="doc-section-body">{children}</div>
    </section>
  );
}
