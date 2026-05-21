import React, { useEffect, useState } from "react";
import { api } from "./api";
import CohortSelector from "./components/CohortSelector";
import MutationBarChart from "./components/MutationBarChart";
import ExpressionBoxplot from "./components/ExpressionBoxplot";
import SurvivalCurve from "./components/SurvivalCurve";

const EMPTY_FILTERS = {
  cancer_type: "BRCA",
  gender: "",
  tumor_stage: "",
  min_age: "",
  max_age: "",
};

export default function App() {
  const [cancerTypes, setCancerTypes] = useState([]);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [cohort, setCohort] = useState(null);
  const [freq, setFreq] = useState(null);
  const [gene, setGene] = useState(null);
  const [expr, setExpr] = useState(null);
  const [surv, setSurv] = useState(null);
  const [error, setError] = useState(null);

  // Strip empty filter fields before sending to the API.
  const clean = (f) =>
    Object.fromEntries(Object.entries(f).filter(([, v]) => v !== "" && v != null));

  useEffect(() => {
    api.cancerTypes().then(setCancerTypes).catch((e) => setError(e.message));
  }, []);

  // Cohort + mutation frequency refresh whenever filters change.
  useEffect(() => {
    const f = clean(filters);
    setError(null);
    Promise.all([api.cohort(f), api.mutationFrequency(f, 20)])
      .then(([c, mf]) => {
        setCohort(c);
        setFreq(mf);
        if (mf.genes.length && !mf.genes.some((g) => g.hugo_symbol === gene)) {
          setGene(mf.genes[0].hugo_symbol);
        }
      })
      .catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  // Expression + survival refresh when the selected gene or cohort changes.
  useEffect(() => {
    if (!gene) return;
    const f = clean(filters);
    api.expressionBoxplot(f, gene).then(setExpr).catch(() => setExpr(null));
    api.survival(f, gene).then(setSurv).catch(() => setSurv(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gene, filters]);

  return (
    <div className="app">
      <header>
        <h1>Cancer Omics Browser</h1>
        <p>TCGA pan-cancer mutation, expression &amp; survival explorer</p>
      </header>

      {error && <div className="error">{error}</div>}

      <div className="layout">
        <aside>
          <CohortSelector
            cancerTypes={cancerTypes}
            filters={filters}
            onChange={setFilters}
            cohort={cohort}
          />
          {gene && (
            <div className="panel">
              <h2>Focus gene</h2>
              <div className="gene-badge">{gene}</div>
            </div>
          )}
        </aside>

        <main>
          <MutationBarChart
            data={freq}
            onSelectGene={setGene}
            selectedGene={gene}
          />
          <div className="chart-row">
            <ExpressionBoxplot data={expr} gene={gene} />
            <SurvivalCurve data={surv} gene={gene} />
          </div>
        </main>
      </div>
    </div>
  );
}
