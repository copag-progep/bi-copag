const NON_NAME_LABELS = new Set(["nao informado", "não informado", "sem atribuicao", "sem atribuição"]);
const NAME_CONNECTORS = new Set(["da", "das", "de", "do", "dos", "e"]);

function normalizeText(value) {
  return String(value ?? "").trim();
}

function cleanWord(word) {
  return word
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]/g, "");
}

export function formatUserNameAsInitials(value) {
  const text = normalizeText(value);
  if (!text) {
    return "";
  }

  if (NON_NAME_LABELS.has(text.toLowerCase())) {
    return text;
  }

  const words = text.split(/\s+/).filter(Boolean);
  if (!words.length) {
    return text;
  }

  const significantWords = words.filter((word, index) => index === 0 || !NAME_CONNECTORS.has(word.toLowerCase()));
  const sourceWords = significantWords.length ? significantWords : words;
  const initials = sourceWords
    .map((word) => cleanWord(word))
    .filter(Boolean)
    .map((word) => word[0].toUpperCase())
    .join("");

  return initials || text;
}
