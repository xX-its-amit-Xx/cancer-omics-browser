import React from "react";
import Plot from "../Plot";

// Why it matters: mutation frequency reveals which genes are recurrently altered in
// a cancer type — the candidate drivers and therapeutic targets.
export default function MutationBarChart({ data, onSelectGene, selectedGene }) {
  if (!data || data.genes.length === 0) return <Empty label="mutation data" />;

  const genes = [...data.genes].reverse();
  return (
    <div className="chart">
      <Plot
        data={[
          {
            type: "bar",
            orientation: "h",
            x: genes.map((g) => g.frequency * 100),
            y: genes.map((g) => g.hugo_symbol),
            marker: {
              color: genes.map((g) =>
                g.hugo_symbol === selectedGene ? "#d6336c" : "#4263eb"
              ),
            },
            hovertemplate:
              "%{y}: %{x:.1f}% (%{customdata}/" +
              data.total_patients +
              ")<extra></extra>",
            customdata: genes.map((g) => g.mutated_patients),
          },
        ]}
        layout={{
          title: `Top mutated genes — ${data.cancer_type}`,
          xaxis: { title: "% of cohort mutated" },
          margin: { l: 90, r: 20, t: 50, b: 40 },
          height: 460,
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: "100%" }}
        onClick={(e) => onSelectGene && onSelectGene(e.points[0].y)}
      />
      <p className="hint">Click a bar to drive the expression & survival charts.</p>
    </div>
  );
}

function Empty({ label }) {
  return <div className="chart empty">No {label} for this cohort.</div>;
}
