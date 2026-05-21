// Thin fetch wrapper. All calls are same-origin under /api (proxied to the backend).
const BASE = "/api";

async function get(path, params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null)
  ).toString();
  const url = `${BASE}${path}${qs ? `?${qs}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  cancerTypes: () => get("/cancer-types"),
  genes: (cancerType) => get("/genes", { cancer_type: cancerType }),
  cohort: (filters) => get("/cohort", filters),
  mutationFrequency: (filters, top = 20) =>
    get("/mutations/frequency", { ...filters, top }),
  expressionBoxplot: (filters, gene) =>
    get("/expression/boxplot", { ...filters, gene }),
  survival: (filters, gene) => get("/survival", { ...filters, gene }),
};
