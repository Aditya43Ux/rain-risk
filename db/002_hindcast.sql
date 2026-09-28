-- Past deterministic ECMWF forecasts (Open-Meteo Previous Runs API), one row per
-- cell, day and lead time. Used to measure forecast skill and to train the ML model.
CREATE TABLE IF NOT EXISTS forecast_hindcast (
    cell_id    INTEGER  NOT NULL REFERENCES grid_cell(id) ON DELETE CASCADE,
    valid_date DATE     NOT NULL,           -- UTC day the forecast is for
    lead_days  SMALLINT NOT NULL,           -- issued this many days before
    model      TEXT     NOT NULL,
    precip_mm  REAL     NOT NULL,           -- forecast daily total
    PRIMARY KEY (cell_id, valid_date, lead_days, model)
);
