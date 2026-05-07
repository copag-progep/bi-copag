export default function Checklist({ items }) {
  return (
    <ul className="doc-checklist">
      {items.map((item, i) => (
        <li key={i} className="doc-checklist-item">
          <span className="doc-checklist-box" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}
