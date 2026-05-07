const VARIANTS = {
  default: { bg: "rgba(39,49,104,0.08)",   color: "#273168" },
  accent:  { bg: "rgba(243,147,32,0.14)",  color: "#d4750e" },
  success: { bg: "rgba(26,122,80,0.10)",   color: "#1a7a50" },
  danger:  { bg: "rgba(191,53,53,0.10)",   color: "#bf3535" },
  purple:  { bg: "rgba(74,20,140,0.10)",   color: "#4a148c" },
  warning: { bg: "rgba(154,108,0,0.12)",   color: "#9a6c00" },
};

export default function PillTag({ children, variant = "default" }) {
  const cfg = VARIANTS[variant] || VARIANTS.default;
  return (
    <span className="doc-pill" style={{ background: cfg.bg, color: cfg.color }}>
      {children}
    </span>
  );
}
