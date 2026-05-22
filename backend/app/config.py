from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+psycopg2://omics:omics@db:5432/omics"
    # Cancer types included in this subset of TCGA.
    cancer_types: list[str] = ["BRCA", "LUAD", "COAD"]

    @field_validator("database_url")
    @classmethod
    def _force_psycopg2_driver(cls, v: str) -> str:
        # Managed Postgres (Render/Heroku) hand out postgres:// or postgresql://
        # URLs with no driver; pin psycopg2 so SQLAlchemy uses the installed one.
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg2://" + v[len("postgresql://"):]
        return v


settings = Settings()
