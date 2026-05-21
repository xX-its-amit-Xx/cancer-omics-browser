from pydantic import BaseModel


class CancerTypeSummary(BaseModel):
    cancer_type: str
    patient_count: int


class CohortSummary(BaseModel):
    cancer_type: str
    patient_count: int
    mutated_patient_count: int
    filters_applied: dict


class GeneFrequency(BaseModel):
    hugo_symbol: str
    mutated_patients: int
    total_patients: int
    frequency: float  # 0..1


class MutationFrequencyResponse(BaseModel):
    cancer_type: str
    total_patients: int
    genes: list[GeneFrequency]


class ExpressionBoxplotResponse(BaseModel):
    gene: str
    cancer_type: str
    mutated: list[float]
    wildtype: list[float]
    unit: str = "log2(TPM+1)"


class SurvivalGroup(BaseModel):
    label: str  # "Mutated" / "Wild-type"
    n: int
    timeline: list[float]  # days
    survival: list[float]  # KM survival probability at each timeline point


class SurvivalResponse(BaseModel):
    gene: str
    cancer_type: str
    groups: list[SurvivalGroup]
    logrank_p: float | None
