// Thin fetch wrapper.
//   * Local/Docker: VITE_API_BASE is unset, so calls go to same-origin "/api"
//     (Vite proxies it to the backend service).
//   * Static hosting (GitHub Pages): VITE_API_BASE is the deployed backend origin,
//     e.g. https://cancer-omics-api.onrender.com, and calls go cross-origin.
const ROOT = import.meta.env.VITE_API_BASE || "";
const BASE = `${ROOT}/api`;

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
