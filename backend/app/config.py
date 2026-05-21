from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+psycopg2://omics:omics@db:5432/omics"
    # Cancer types included in this subset of TCGA.
    cancer_types: list[str] = ["BRCA", "LUAD", "COAD"]


settings = Settings()
