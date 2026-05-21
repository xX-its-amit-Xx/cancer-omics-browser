"""Generate a small, biologically plausible synthetic TCGA subset.

This is the offline fallback that guarantees `docker compose up` produces a fully
functional app without network access. The numbers are randomized but anchored to
known cancer-genomics facts (e.g. PIK3CA/TP53 frequency in BRCA, KRAS in LUAD/COAD,
APC in COAD) so the charts are realistic. Replace with real data via ingest_gdc.py.
"""
from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from app.models import Expression, Mutation, Patient

RNG = np.random.default_rng(42)

VARIANT_CLASSES = [
    "Missense_Mutation",
    "Nonsense_Mutation",
    "Frame_Shift_Del",
    "Splice_Site",
    "In_Frame_Del",
]
STAGES = ["Stage I", "Stage II", "Stage III", "Stage IV"]

# Per cancer type: number of patients and a {gene: mutation_frequency} map drawn
# from canonical TCGA marker-paper frequencies.
COHORTS = {
    "BRCA": {
        "n": 200,
        "genes": {
            "PIK3CA": 0.35, "TP53": 0.30, "CDH1": 0.13, "GATA3": 0.11,
            "MAP3K1": 0.09, "MLL3": 0.07, "PTEN": 0.06, "RB1": 0.04,
        },
    },
    "LUAD": {
        "n": 160,
        "genes": {
            "TP53": 0.46, "KRAS": 0.33, "EGFR": 0.14, "STK11": 0.17,
            "KEAP1": 0.17, "NF1": 0.11, "BRAF": 0.07, "MET": 0.07,
        },
    },
    "COAD": {
        "n": 140,
        "genes": {
            "APC": 0.70, "TP53": 0.55, "KRAS": 0.42, "PIK3CA": 0.18,
            "SMAD4": 0.13, "FBXW7": 0.11, "NRAS": 0.07, "BRAF": 0.10,
        },
    },
}

# Genes whose loss-of-function lowers their own expression (tumor suppressors),
# vs oncogenes where mutation does not reduce expression. Used to shape boxplots.
TUMOR_SUPPRESSORS = {"TP53", "APC", "PTEN", "RB1", "CDH1", "SMAD4", "STK11", "NF1", "FBXW7", "KEAP1"}


def _barcode(ct: str, i: int) -> str:
    return f"TCGA-{ct[:2]}-{1000 + i}"


def generate(session: Session) -> None:
    patients: list[Patient] = []
    mutations: list[Mutation] = []
    expressions: list[Expression] = []

    for ct, spec in COHORTS.items():
        genes = spec["genes"]
        for i in range(spec["n"]):
            barcode = _barcode(ct, i)
            gender = "female" if ct == "BRCA" else RNG.choice(["male", "female"])
            age = int(np.clip(RNG.normal(62, 11), 28, 90))
            stage = RNG.choice(STAGES, p=[0.25, 0.35, 0.28, 0.12])

            # Decide mutation status per gene for this patient.
            mutated_genes: set[str] = set()
            for gene, freq in genes.items():
                if RNG.random() < freq:
                    mutated_genes.add(gene)
                    mutations.append(
                        Mutation(
                            patient_barcode=barcode,
                            cancer_type=ct,
                            hugo_symbol=gene,
                            variant_classification=str(RNG.choice(VARIANT_CLASSES)),
                            variant_type="SNP",
                            chromosome=str(RNG.integers(1, 23)),
                            start_position=int(RNG.integers(1_000_000, 200_000_000)),
                            hgvsp_short=f"p.{RNG.choice(list('ARNDCEQGHILKMFPSTWYV'))}{RNG.integers(1, 800)}{RNG.choice(list('ARNDCEQGHILKMFPSTWYV'))}",
                        )
                    )

            # Survival: baseline; TP53 / KRAS mutation worsens prognosis.
            risk = 0.0
            if "TP53" in mutated_genes:
                risk += 0.6
            if "KRAS" in mutated_genes:
                risk += 0.3
            base_time = RNG.exponential(scale=1800 / (1 + risk))
            os_time = int(np.clip(base_time, 30, 4000))
            # Higher risk -> more likely death observed; otherwise censored.
            death_prob = np.clip(0.35 + 0.25 * risk, 0, 0.9)
            os_event = int(RNG.random() < death_prob)
            vital = "Dead" if os_event else "Alive"

            patients.append(
                Patient(
                    patient_barcode=barcode,
                    cancer_type=ct,
                    gender=str(gender),
                    age_at_diagnosis=age,
                    tumor_stage=str(stage),
                    vital_status=vital,
                    os_time=os_time,
                    os_event=os_event,
                )
            )

            # Expression for every gene in the panel for this patient.
            for gene in genes:
                base = RNG.normal(8.0, 1.2)  # log2(TPM+1) baseline
                if gene in mutated_genes and gene in TUMOR_SUPPRESSORS:
                    base -= RNG.normal(2.0, 0.6)  # LoF lowers expression
                elif gene in mutated_genes:
                    base += RNG.normal(1.0, 0.5)  # oncogene activation/up
                expressions.append(
                    Expression(
                        patient_barcode=barcode,
                        cancer_type=ct,
                        gene=gene,
                        value=float(np.clip(base, 0, 16)),
                    )
                )

    session.add_all(patients)
    session.add_all(mutations)
    session.add_all(expressions)
    session.commit()
    print(
        f"Seeded {len(patients)} patients, {len(mutations)} mutations, "
        f"{len(expressions)} expression rows."
    )
