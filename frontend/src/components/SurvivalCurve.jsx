import React from "react";
import Plot from "../Plot";

// Why it matters: a Kaplan-Meier curve splits patients by mutation status and asks the
// clinical question that matters most — does carrying this mutation change how long
// patients survive? The log-rank p-value tests whether the gap is statistically real.
export default function SurvivalCurve({ data, gene }) {
  if (!data) return <div className="chart empty">Select a gene to see survival.</div>;

  const colors = { Mutated: "#d6336c", "Wild-type": "#4263eb" };
  const traces = data.groups.map((g) => ({
    type: "scatter",
    mode: "lines",
    line: { shape: "hv", color: colors[g.label], width: 2 },
    name: `${g.label} (n=${g.n})`,
    x: g.timeline,
    y: g.survival,
  }));

  const p = data.logrank_p;
  const pText =
    p == null ? "n/a" : p < 0.001 ? "< 0.001" : p.toFixed(3);

  return (
    <div className="chart">
      <Plot
        data={traces}
        layout={{
          title: `Overall survival by ${data.gene} status (log-rank p = ${pText})`,
          xaxis: { title: "Days" },
          yaxis: { title: "Survival probability", range: [0, 1] },
          margin: { l: 60, r: 20, t: 50, b: 40 },
          height: 460,
          legend: { x: 0.6, y: 0.95 },
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: "100%" }}
      />
    </div>
  );
}
