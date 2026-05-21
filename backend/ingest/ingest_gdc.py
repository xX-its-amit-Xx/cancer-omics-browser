"""Pull a small real TCGA subset from the public GDC API and load it to Postgres.

Scope (kept deliberately small so it runs in minutes):
  * Clinical + overall-survival fields for TCGA-BRCA / -LUAD / -COAD cases.
  * Open-access somatic mutations (SSM occurrences) restricted to a curated gene panel.
  * Gene-level expression (TPM) parsed from a capped number of STAR-Counts files.

All network access is via the documented GDC endpoints under https://api.gdc.cancer.gov.
If the network is unavailable, callers should fall back to seed_data.generate().

Usage:
    python -m ingest.ingest_gdc --cases-per-type 60 --expr-samples 40
"""
from __future__ import annotations

import argparse
import io
import math

import pandas as pd
import requests
from sqlalchemy.orm import Session

from app.models import Expression, Mutation, Patient
from .seed_data import COHORTS

GDC = "https://api.gdc.cancer.gov"
PROJECTS = {"BRCA": "TCGA-BRCA", "LUAD": "TCGA-LUAD", "COAD": "TCGA-COAD"}


def _panel(ct: str) -> list[str]:
    return list(COHORTS[ct]["genes"].keys())


def _os_fields(case: dict) -> tuple[int | None, int | None]:
    """Derive (os_time_days, os_event) from a GDC case's diagnosis/demographic."""
    demo = case.get("demographic", {}) or {}
    diagnoses = case.get("diagnoses", []) or [{}]
    diag = diagnoses[0] if diagnoses else {}
    vital = (demo.get("vital_status") or "").lower()
    days_to_death = demo.get("days_to_death")
    days_to_followup = diag.get("days_to_last_follow_up")
    if vital == "dead" and days_to_death is not None:
        return int(days_to_death), 1
    if days_to_followup is not None:
        return int(days_to_followup), 0
    return None, None


def fetch_cases(ct: str, limit: int) -> list[Patient]:
    project = PROJECTS[ct]
    body = {
        "filters": {
            "op": "in",
            "content": {"field": "project.project_id", "value": [project]},
        },
        "fields": ",".join(
            [
                "submitter_id",
                "demographic.gender",
                "demographic.vital_status",
                "demographic.days_to_death",
                "diagnoses.age_at_diagnosis",
                "diagnoses.days_to_last_follow_up",
                "diagnoses.ajcc_pathologic_stage",
            ]
        ),
        "format": "json",
        "size": str(limit),
        "expand": "demographic,diagnoses",
    }
    r = requests.post(f"{GDC}/cases", json=body, timeout=60)
    r.raise_for_status()
    hits = r.json()["data"]["hits"]

    patients = []
    for c in hits:
        demo = c.get("demographic", {}) or {}
        diag = (c.get("diagnoses") or [{}])[0]
        os_time, os_event = _os_fields(c)
        age_days = diag.get("age_at_diagnosis")
        stage = diag.get("ajcc_pathologic_stage") or "Unknown"
        patients.append(
            Patient(
                patient_barcode=c["submitter_id"],
                cancer_type=ct,
                gender=(demo.get("gender") or "unknown").lower(),
                age_at_diagnosis=int(age_days / 365) if age_days else None,
                tumor_stage=stage,
                vital_status=(demo.get("vital_status") or "Unknown").capitalize(),
                os_time=os_time,
                os_event=os_event,
            )
        )
    return patients


def fetch_mutations(ct: str, barcodes: set[str]) -> list[Mutation]:
    project = PROJECTS[ct]
    body = {
        "filters": {
            "op": "and",
            "content": [
                {"op": "in", "content": {"field": "case.project.project_id", "value": [project]}},
                {"op": "in", "content": {"field": "ssm.consequence.transcript.gene.symbol", "value": _panel(ct)}},
            ],
        },
        "fields": ",".join(
            [
                "case.submitter_id",
                "ssm.consequence.transcript.gene.symbol",
                "ssm.consequence.transcript.aa_change",
                "ssm.mutation_subtype",
                "ssm.chromosome",
                "ssm.start_position",
            ]
        ),
        "format": "json",
        "size": "5000",
    }
    r = requests.post(f"{GDC}/ssm_occurrences", json=body, timeout=120)
    r.raise_for_status()
    hits = r.json()["data"]["hits"]

    mutations = []
    for h in hits:
        case = h.get("case", {}) or {}
        barcode = case.get("submitter_id")
        if barcode not in barcodes:
            continue
        ssm = h.get("ssm", {}) or {}
        cons = (ssm.get("consequence") or [{}])[0]
        gene = (((cons.get("transcript") or {}).get("gene") or {}).get("symbol"))
        if not gene:
            continue
        mutations.append(
            Mutation(
                patient_barcode=barcode,
                cancer_type=ct,
                hugo_symbol=gene,
                variant_classification=ssm.get("mutation_subtype"),
                variant_type="SNP",
                chromosome=str(ssm.get("chromosome")),
                start_position=ssm.get("start_position"),
                hgvsp_short=((cons.get("transcript") or {}).get("aa_change")),
            )
        )
    return mutations


def fetch_expression(ct: str, barcodes: set[str], n_samples: int) -> list[Expression]:
    """Download a capped number of open STAR-Counts files and extract panel TPMs."""
    project = PROJECTS[ct]
    body = {
        "filters": {
            "op": "and",
            "content": [
                {"op": "in", "content": {"field": "cases.project.project_id", "value": [project]}},
                {"op": "in", "content": {"field": "data_type", "value": ["Gene Expression Quantification"]}},
                {"op": "in", "content": {"field": "analysis.workflow_type", "value": ["STAR - Counts"]}},
                {"op": "in", "content": {"field": "access", "value": ["open"]}},
            ],
        },
        "fields": "file_id,cases.submitter_id",
        "format": "json",
        "size": str(n_samples * 2),
    }
    r = requests.post(f"{GDC}/files", json=body, timeout=60)
    r.raise_for_status()
    hits = r.json()["data"]["hits"]

    panel = set(_panel(ct))
    expressions: list[Expression] = []
    seen: set[str] = set()
    for h in hits:
        if len(seen) >= n_samples:
            break
        cases = h.get("cases") or [{}]
        barcode = cases[0].get("submitter_id")
        if barcode not in barcodes or barcode in seen:
            continue
        file_id = h["file_id"]
        try:
            data = requests.get(f"{GDC}/data/{file_id}", timeout=120).content
            df = pd.read_csv(io.BytesIO(data), sep="\t", comment="#")
        except Exception as exc:  # noqa: BLE001 - skip unreadable files
            print(f"  skip {file_id}: {exc}")
            continue
        df = df[df["gene_name"].isin(panel)]
        for _, row in df.iterrows():
            tpm = row.get("tpm_unstranded")
            if pd.isna(tpm):
                continue
            expressions.append(
                Expression(
                    patient_barcode=barcode,
                    cancer_type=ct,
                    gene=row["gene_name"],
                    value=float(math.log2(float(tpm) + 1)),
                )
            )
        seen.add(barcode)
    return expressions


def ingest(session: Session, cases_per_type: int, expr_samples: int) -> None:
    for ct in PROJECTS:
        print(f"[{ct}] fetching clinical cases...")
        patients = fetch_cases(ct, cases_per_type)
        barcodes = {p.patient_barcode for p in patients}
        session.add_all(patients)
        session.commit()

        print(f"[{ct}] fetching mutations...")
        muts = fetch_mutations(ct, barcodes)
        session.add_all(muts)
        session.commit()

        print(f"[{ct}] fetching expression for up to {expr_samples} samples...")
        exprs = fetch_expression(ct, barcodes, expr_samples)
        session.add_all(exprs)
        session.commit()
        print(f"[{ct}] {len(patients)} patients, {len(muts)} mutations, {len(exprs)} expr rows.")


def main() -> None:
    from app.database import SessionLocal, engine, Base

    parser = argparse.ArgumentParser(description="Ingest a small TCGA subset from GDC.")
    parser.add_argument("--cases-per-type", type=int, default=60)
    parser.add_argument("--expr-samples", type=int, default=40)
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        ingest(session, args.cases_per_type, args.expr_samples)
    finally:
        session.close()


if __name__ == "__main__":
    main()
