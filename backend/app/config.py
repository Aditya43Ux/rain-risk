from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://rain:rain@localhost:5432/rain"
    bbox: str = "76.5,12.0,78.5,14.0"  # west,south,east,north
    grid_step: float = 0.25
    ensemble_model: str = "ecmwf_ifs025"
    display_model: str = "lgbm_v1"
    timezone: str = "auto"
    rain_threshold_mm: float = 1.0
    cors_origins: str = "http://localhost:5173"


settings = Settings()
