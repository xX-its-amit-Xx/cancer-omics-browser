"""Entrypoint used at container start to ensure the DB has data.

Default behavior: create tables, and if the patients table is empty, populate it.
  * DATA_SOURCE=synthetic (default) -> generate the offline synthetic subset.
  * DATA_SOURCE=gdc                 -> pull a small real subset from the GDC API,
                                       falling back to synthetic on any failure.
Re-running is idempotent: if data already exists, it does nothing.
"""
from __future__ import annotations

import os
import sys
import time

from sqlalchemy import func
from sqlalchemy.exc import OperationalError

from app.database import Base, SessionLocal, engine
from app.models import Patient
from .seed_data import generate


def _wait_for_db(retries: int = 30, delay: float = 2.0) -> None:
    for attempt in range(retries):
        try:
            with engine.connect():
                return
        except OperationalError:
            print(f"DB not ready (attempt {attempt + 1}/{retries})...")
            time.sleep(delay)
    raise SystemExit("Database never became available.")


def main() -> None:
    _wait_for_db()
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        existing = session.query(func.count(Patient.patient_barcode)).scalar()
        if existing:
            print(f"Data already present ({existing} patients); skipping load.")
            return

        source = os.getenv("DATA_SOURCE", "synthetic").lower()
        if source == "gdc":
            try:
                from .ingest_gdc import ingest

                cases = int(os.getenv("GDC_CASES_PER_TYPE", "60"))
                expr = int(os.getenv("GDC_EXPR_SAMPLES", "40"))
                ingest(session, cases, expr)
                if session.query(func.count(Patient.patient_barcode)).scalar():
                    return
                print("GDC ingest produced no rows; falling back to synthetic.")
            except Exception as exc:  # noqa: BLE001
                print(f"GDC ingest failed ({exc}); falling back to synthetic.")
                session.rollback()

        generate(session)
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
