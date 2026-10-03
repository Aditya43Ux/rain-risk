from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = "postgresql://rain:rain@localhost:5432/rain"
    bbox: str = "76.5,12.0,78.5,14.0"  # west,south,east,north
    grid_step: float = 0.25
    ensemble_model: str = "ecmwf_ifs025"
    display_model: str = "lgbm_v1"
    timezone: str = "GMT"  # IMERG days are UTC days; forecasts must match
    rain_threshold_mm: float = 1.0
    cors_origins: str = "http://localhost:5173"

    @property
    def bbox_bounds(self) -> tuple[float, float, float, float]:
        west, south, east, north = (float(x) for x in self.bbox.split(","))
        return west, south, east, north


settings = Settings()
