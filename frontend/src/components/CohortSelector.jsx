import React from "react";

const STAGES = ["", "Stage I", "Stage II", "Stage III", "Stage IV"];

export default function CohortSelector({
  cancerTypes,
  filters,
  onChange,
  cohort,
}) {
  const set = (key) => (e) => onChange({ ...filters, [key]: e.target.value });

  return (
    <div className="panel">
      <h2>Cohort</h2>
      <label>
        Cancer type
        <select value={filters.cancer_type} onChange={set("cancer_type")}>
          {cancerTypes.map((c) => (
            <option key={c.cancer_type} value={c.cancer_type}>
              {c.cancer_type} (n={c.patient_count})
            </option>
          ))}
        </select>
      </label>

      <label>
        Gender
        <select value={filters.gender} onChange={set("gender")}>
          <option value="">Any</option>
          <option value="female">Female</option>
          <option value="male">Male</option>
        </select>
      </label>

      <label>
        Tumor stage
        <select value={filters.tumor_stage} onChange={set("tumor_stage")}>
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {s || "Any"}
            </option>
          ))}
        </select>
      </label>

      <div className="row">
        <label>
          Min age
          <input
            type="number"
            value={filters.min_age}
            onChange={set("min_age")}
            min="0"
            max="100"
          />
        </label>
        <label>
          Max age
          <input
            type="number"
            value={filters.max_age}
            onChange={set("max_age")}
            min="0"
            max="100"
          />
        </label>
      </div>

      {cohort && (
        <div className="cohort-summary">
          <strong>{cohort.patient_count}</strong> patients ·{" "}
          <strong>{cohort.mutated_patient_count}</strong> with mutations
        </div>
      )}
    </div>
  );
}
