import React from "react";
import Plot from "../Plot";

// Why it matters: comparing a gene's expression between mutated and wild-type tumors
// shows whether a mutation changes how much the gene is expressed (e.g. loss-of-function
// often lowers tumor-suppressor expression).
export default function ExpressionBoxplot({ data, gene }) {
  if (!data) return <div className="chart empty">Select a gene to see expression.</div>;
  if (data.mutated.length === 0 && data.wildtype.length === 0)
    return <div className="chart empty">No expression for {gene}.</div>;

  return (
    <div className="chart">
      <Plot
        data={[
          {
            type: "box",
            name: `Mutated (n=${data.mutated.length})`,
            y: data.mutated,
            boxpoints: "all",
            jitter: 0.4,
            marker: { color: "#d6336c" },
          },
          {
            type: "box",
            name: `Wild-type (n=${data.wildtype.length})`,
            y: data.wildtype,
            boxpoints: "all",
            jitter: 0.4,
            marker: { color: "#4263eb" },
          },
        ]}
        layout={{
          title: `${data.gene} expression by mutation status`,
          yaxis: { title: data.unit },
          margin: { l: 60, r: 20, t: 50, b: 40 },
          height: 460,
          showlegend: false,
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: "100%" }}
      />
    </div>
  );
}
