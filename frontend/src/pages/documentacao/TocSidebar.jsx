import { useEffect, useState } from "react";

const SECTIONS = [
  { id: "s01", num: "01", label: "O que é o SEI Analytics" },
  { id: "s02", num: "02", label: "Arquitetura" },
  { id: "s03", num: "03", label: "Stack tecnológica" },
  { id: "s04", num: "04", label: "Modelo de dados" },
  { id: "s05", num: "05", label: "Backend e endpoints" },
  { id: "s06", num: "06", label: "Frontend" },
  { id: "s07", num: "07", label: "Automação" },
  { id: "s08", num: "08", label: "Segurança e auditoria" },
  { id: "s09", num: "09", label: "Configuração" },
  { id: "s10", num: "10", label: "Manutenção" },
  { id: "s11", num: "11", label: "Transição de gestão" },
  { id: "s12", num: "12", label: "Histórico" },
];

export default function TocSidebar() {
  const [active, setActive] = useState("s01");

  useEffect(() => {
    const observers = SECTIONS.map(({ id }) => {
      const el = document.getElementById(id);
      if (!el) return null;
      const obs = new IntersectionObserver(
        ([entry]) => { if (entry.isIntersecting) setActive(id); },
        { rootMargin: "-20% 0px -70% 0px" }
      );
      obs.observe(el);
      return obs;
    }).filter(Boolean);

    return () => observers.forEach((o) => o.disconnect());
  }, []);

  return (
    <nav className="doc-toc">
      <div className="doc-toc-title">Índice</div>
      <ol className="doc-toc-list">
        {SECTIONS.map(({ id, num, label }) => (
          <li key={id}>
            <a
              href={`#${id}`}
              className={`doc-toc-item ${active === id ? "active" : ""}`}
            >
              <span className="doc-toc-num">{num}</span>
              <span className="doc-toc-label">{label}</span>
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
