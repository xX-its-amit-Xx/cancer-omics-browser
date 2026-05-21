"""Shared clinical-filter parsing applied to Patient queries."""
from dataclasses import dataclass

from sqlalchemy.orm import Query

from .models import Patient


@dataclass
class CohortFilters:
    cancer_type: str
    gender: str | None = None
    min_age: int | None = None
    max_age: int | None = None
    tumor_stage: str | None = None
    vital_status: str | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


def apply_filters(query: Query, f: CohortFilters) -> Query:
    query = query.filter(Patient.cancer_type == f.cancer_type)
    if f.gender:
        query = query.filter(Patient.gender == f.gender)
    if f.min_age is not None:
        query = query.filter(Patient.age_at_diagnosis >= f.min_age)
    if f.max_age is not None:
        query = query.filter(Patient.age_at_diagnosis <= f.max_age)
    if f.tumor_stage:
        query = query.filter(Patient.tumor_stage == f.tumor_stage)
    if f.vital_status:
        query = query.filter(Patient.vital_status == f.vital_status)
    return query
