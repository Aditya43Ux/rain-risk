CREATE EXTENSION IF NOT EXISTS postgis;

-- One row per grid cell. lat/lon are the cell centre.
CREATE TABLE IF NOT EXISTS grid_cell (
    id       SERIAL PRIMARY KEY,
    lat      DOUBLE PRECISION NOT NULL,
    lon      DOUBLE PRECISION NOT NULL,
    centroid geometry(Point, 4326)   NOT NULL,
    geom     geometry(Polygon, 4326) NOT NULL,
    UNIQUE (lat, lon)
);
CREATE INDEX IF NOT EXISTS grid_cell_centroid_gix      ON grid_cell USING GIST (centroid);
CREATE INDEX IF NOT EXISTS grid_cell_centroid_geog_gix ON grid_cell USING GIST ((centroid::geography));
CREATE INDEX IF NOT EXISTS grid_cell_geom_gix          ON grid_cell USING GIST (geom);

-- Every fetch is kept (fetched_at is part of the key). Open-Meteo only keeps
-- individual ensemble members for a few days, so this table is the only archive.
CREATE TABLE IF NOT EXISTS forecast_daily (
    cell_id    INTEGER     NOT NULL REFERENCES grid_cell(id) ON DELETE CASCADE,
    valid_date DATE        NOT NULL,
    model      TEXT        NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    p_rain     REAL        NOT NULL,  -- chance the daily total >= threshold (ensemble share or ML output)
    mean_mm    REAL,
    p90_mm     REAL,
    n_members  SMALLINT,
    PRIMARY KEY (cell_id, valid_date, model, fetched_at)
);
-- The API reads the newest run of a model: max(fetched_at), then its rows.
CREATE INDEX IF NOT EXISTS forecast_daily_model_fetched_ix ON forecast_daily (model, fetched_at);
DROP INDEX IF EXISTS forecast_daily_date_ix;  -- superseded by the index above
DROP VIEW IF EXISTS forecast_latest;          -- older installs: replaced by the latest-run queries

-- Observed rainfall (NASA IMERG, see app/observe_imerg.py): the training target.
CREATE TABLE IF NOT EXISTS observation_daily (
    cell_id  INTEGER NOT NULL REFERENCES grid_cell(id) ON DELETE CASCADE,
    obs_date DATE    NOT NULL,
    rain_mm  REAL    NOT NULL,
    source   TEXT    NOT NULL,
    PRIMARY KEY (cell_id, obs_date, source)
);
