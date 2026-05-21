from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from .database import Base


class Patient(Base):
    """One row per TCGA patient, carrying clinical + survival fields."""

    __tablename__ = "patients"

    patient_barcode = Column(String, primary_key=True)  # e.g. TCGA-A1-A0SB
    cancer_type = Column(String, index=True, nullable=False)  # BRCA / LUAD / COAD
    gender = Column(String, index=True)  # male / female
    age_at_diagnosis = Column(Integer)  # years
    tumor_stage = Column(String, index=True)  # Stage I..IV / Unknown
    vital_status = Column(String)  # Alive / Dead
    # Overall-survival fields (days). os_event = 1 if death observed, else 0 (censored).
    os_time = Column(Integer)
    os_event = Column(Integer)

    mutations = relationship("Mutation", back_populates="patient")
    expressions = relationship("Expression", back_populates="patient")


class Mutation(Base):
    """Somatic mutation calls (MC3 MAF subset). One row per variant per sample."""

    __tablename__ = "mutations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_barcode = Column(
        String, ForeignKey("patients.patient_barcode"), index=True, nullable=False
    )
    cancer_type = Column(String, index=True, nullable=False)
    hugo_symbol = Column(String, index=True, nullable=False)  # gene
    variant_classification = Column(String)  # Missense_Mutation, Nonsense_Mutation, ...
    variant_type = Column(String)  # SNP / INS / DEL
    chromosome = Column(String)
    start_position = Column(Integer)
    hgvsp_short = Column(String)  # protein change, e.g. p.R175H

    patient = relationship("Patient", back_populates="mutations")

    __table_args__ = (
        Index("ix_mut_cancer_gene", "cancer_type", "hugo_symbol"),
    )


class Expression(Base):
    """RNA-seq expression in long format. One row per (patient, gene)."""

    __tablename__ = "expression"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_barcode = Column(
        String, ForeignKey("patients.patient_barcode"), index=True, nullable=False
    )
    cancer_type = Column(String, index=True, nullable=False)
    gene = Column(String, index=True, nullable=False)
    value = Column(Float, nullable=False)  # log2(TPM + 1)

    patient = relationship("Patient", back_populates="expressions")

    __table_args__ = (
        Index("ix_expr_cancer_gene", "cancer_type", "gene"),
    )
