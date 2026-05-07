const COLORS = {
  GET:    { bg: "rgba(26,122,80,0.12)",   color: "#1a7a50" },
  POST:   { bg: "rgba(243,147,32,0.14)",  color: "#d4750e" },
  PATCH:  { bg: "rgba(154,108,0,0.14)",   color: "#9a6c00" },
  DELETE: { bg: "rgba(191,53,53,0.12)",   color: "#bf3535" },
};

export default function MethodBadge({ method }) {
  const cfg = COLORS[method] || COLORS.GET;
  return (
    <span className="doc-method-badge" style={{ background: cfg.bg, color: cfg.color }}>
      {method}
    </span>
  );
}
