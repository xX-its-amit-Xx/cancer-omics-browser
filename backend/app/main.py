from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import schemas
from .analytics import km_curve, logrank_pvalue
from .database import get_db
from .filters import CohortFilters, apply_filters
from .models import Expression, Mutation, Patient

app = FastAPI(
    title="Cancer Omics Browser API",
    description="Explore TCGA pan-cancer mutation, expression, and survival data.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def cohort_filters(
    cancer_type: str = Query(..., description="TCGA cancer type, e.g. BRCA"),
    gender: str | None = Query(None),
    min_age: int | None = Query(None),
    max_age: int | None = Query(None),
    tumor_stage: str | None = Query(None),
    vital_status: str | None = Query(None),
) -> CohortFilters:
    return CohortFilters(
        cancer_type=cancer_type,
        gender=gender,
        min_age=min_age,
        max_age=max_age,
        tumor_stage=tumor_stage,
        vital_status=vital_status,
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/cancer-types", response_model=list[schemas.CancerTypeSummary])
def cancer_types(db: Session = Depends(get_db)):
    """List available cancer types with patient counts."""
    rows = (
        db.query(Patient.cancer_type, func.count(Patient.patient_barcode))
        .group_by(Patient.cancer_type)
        .order_by(Patient.cancer_type)
        .all()
    )
    return [schemas.CancerTypeSummary(cancer_type=ct, patient_count=n) for ct, n in rows]


@app.get("/api/cohort", response_model=schemas.CohortSummary)
def cohort(f: CohortFilters = Depends(cohort_filters), db: Session = Depends(get_db)):
    """Summarize a filtered cohort: total patients and how many carry any mutation."""
    base = apply_filters(db.query(Patient.patient_barcode), f)
    barcodes = [r[0] for r in base.all()]
    patient_count = len(barcodes)
    mutated = 0
    if barcodes:
        mutated = (
            db.query(func.count(func.distinct(Mutation.patient_barcode)))
            .filter(Mutation.patient_barcode.in_(barcodes))
            .scalar()
        )
    return schemas.CohortSummary(
        cancer_type=f.cancer_type,
        patient_count=patient_count,
        mutated_patient_count=mutated,
        filters_applied=f.as_dict(),
    )


@app.get("/api/genes", response_model=list[str])
def genes(cancer_type: str, db: Session = Depends(get_db)):
    """Genes that have both mutation and expression data for a cancer type."""
    mut_genes = {
        r[0]
        for r in db.query(Mutation.hugo_symbol)
        .filter(Mutation.cancer_type == cancer_type)
        .distinct()
        .all()
    }
    expr_genes = {
        r[0]
        for r in db.query(Expression.gene)
        .filter(Expression.cancer_type == cancer_type)
        .distinct()
        .all()
    }
    return sorted(mut_genes & expr_genes)


@app.get("/api/mutations/frequency", response_model=schemas.MutationFrequencyResponse)
def mutation_frequency(
    f: CohortFilters = Depends(cohort_filters),
    top: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Per-gene mutation frequency = (patients mutated in gene) / (cohort patients)."""
    barcodes = [r[0] for r in apply_filters(db.query(Patient.patient_barcode), f).all()]
    total = len(barcodes)
    if total == 0:
        return schemas.MutationFrequencyResponse(
            cancer_type=f.cancer_type, total_patients=0, genes=[]
        )
    rows = (
        db.query(
            Mutation.hugo_symbol,
            func.count(func.distinct(Mutation.patient_barcode)),
        )
        .filter(Mutation.patient_barcode.in_(barcodes))
        .group_by(Mutation.hugo_symbol)
        .order_by(func.count(func.distinct(Mutation.patient_barcode)).desc())
        .limit(top)
        .all()
    )
    genes = [
        schemas.GeneFrequency(
            hugo_symbol=g,
            mutated_patients=n,
            total_patients=total,
            frequency=round(n / total, 4),
        )
        for g, n in rows
    ]
    return schemas.MutationFrequencyResponse(
        cancer_type=f.cancer_type, total_patients=total, genes=genes
    )


@app.get("/api/expression/boxplot", response_model=schemas.ExpressionBoxplotResponse)
def expression_boxplot(
    gene: str,
    f: CohortFilters = Depends(cohort_filters),
    db: Session = Depends(get_db),
):
    """Expression of `gene` split by whether each patient is mutated in `gene`."""
    barcodes = [r[0] for r in apply_filters(db.query(Patient.patient_barcode), f).all()]
    if not barcodes:
        raise HTTPException(status_code=404, detail="No patients match this cohort")

    mutated_barcodes = {
        r[0]
        for r in db.query(Mutation.patient_barcode)
        .filter(
            Mutation.patient_barcode.in_(barcodes),
            Mutation.hugo_symbol == gene,
        )
        .distinct()
        .all()
    }

    expr_rows = (
        db.query(Expression.patient_barcode, Expression.value)
        .filter(
            Expression.patient_barcode.in_(barcodes),
            Expression.gene == gene,
        )
        .all()
    )
    if not expr_rows:
        raise HTTPException(
            status_code=404, detail=f"No expression data for {gene} in {f.cancer_type}"
        )

    mutated, wildtype = [], []
    for barcode, value in expr_rows:
        (mutated if barcode in mutated_barcodes else wildtype).append(float(value))

    return schemas.ExpressionBoxplotResponse(
        gene=gene, cancer_type=f.cancer_type, mutated=mutated, wildtype=wildtype
    )


@app.get("/api/survival", response_model=schemas.SurvivalResponse)
def survival(
    gene: str,
    f: CohortFilters = Depends(cohort_filters),
    db: Session = Depends(get_db),
):
    """Kaplan-Meier overall survival stratified by mutation status of `gene`."""
    patients = apply_filters(
        db.query(Patient.patient_barcode, Patient.os_time, Patient.os_event), f
    ).all()
    if not patients:
        raise HTTPException(status_code=404, detail="No patients match this cohort")

    mutated_barcodes = {
        r[0]
        for r in db.query(Mutation.patient_barcode)
        .filter(
            Mutation.cancer_type == f.cancer_type,
            Mutation.hugo_symbol == gene,
        )
        .distinct()
        .all()
    }

    groups = {"Mutated": ([], []), "Wild-type": ([], [])}
    for barcode, os_time, os_event in patients:
        if os_time is None or os_event is None:
            continue
        key = "Mutated" if barcode in mutated_barcodes else "Wild-type"
        groups[key][0].append(float(os_time))
        groups[key][1].append(int(os_event))

    out_groups = []
    for label, (times, events) in groups.items():
        timeline, surv = km_curve(times, events)
        out_groups.append(
            schemas.SurvivalGroup(
                label=label, n=len(times), timeline=timeline, survival=surv
            )
        )

    p = logrank_pvalue(
        groups["Mutated"][0],
        groups["Mutated"][1],
        groups["Wild-type"][0],
        groups["Wild-type"][1],
    )

    return schemas.SurvivalResponse(
        gene=gene, cancer_type=f.cancer_type, groups=out_groups, logrank_p=p
    )
