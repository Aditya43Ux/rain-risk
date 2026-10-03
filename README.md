# Rain risk: localized rain-probability maps

"What's the chance of rain around me?" for every ~25 km grid square in a region, for the next 8 days.
A LightGBM model turns ECMWF forecasts into calibrated rain probabilities, trained against NASA
satellite rainfall (GPM IMERG).

```
Open-Meteo (ECMWF) ──► app.predict ──► PostGIS ──► FastAPI ──► React + TypeScript
                       (LightGBM)      forecast_daily  /api/...   map, week playback,
NASA IMERG ──► app.observe_imerg ──►   observation_daily          nearby list, 8-day chart
Open-Meteo past runs ──► app.backfill_forecasts ──► forecast_hindcast ──► ml.train_model
```

## Run it

Needs Docker, Python 3.10+, Node 18+.

```bash
# 1. database (PostGIS)
docker compose up -d

# 2. backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # then edit BBOX to your region
python -m app.migrate                                   # create/update the schema (safe to re-run)
python -m app.seed_grid                                 # create the grid cells
python -m app.predict                                   # live ML forecast (needs a trained model, below)
uvicorn app.main:app --reload                           # http://localhost:8000/docs

# 3. frontend (new terminal)
cd frontend
npm install
npm run dev                                             # http://localhost:5173
```

Search for a town, use your location or click the map. The side panel shows the chance of rain
there, the squares within 10/25/50 km with direction and distance, and the week ahead. "Play week"
animates the map through the days.

## Train the model

The model learns from past forecasts paired with what actually fell:

```bash
python -m app.backfill_forecasts --start 2024-06-01 --end 2026-09-23   # past ECMWF runs, lead 1-7 days
python -m app.observe_imerg --start 2024-06-01 --end 2026-09-23        # NASA IMERG (free Earthdata login)
python -m ml.train_model                  # evaluate: train on other years, test on 2026
python -m ml.train_model --final          # train on everything, save models/rain_lgbm.joblib
```

`ml.train_model` compares the model with climatology, raw ECMWF yes/no and isotonic-calibrated
ECMWF (the baseline to beat), by lead time and with leave-one-year-out.

## Keep it fresh

Two jobs, both safe to re-run:

| Job | What | When |
| --- | --- | --- |
| `run_ingest.bat` | `app.ingest` (raw 51-member ensemble, archived) then `app.predict` (what the map shows) | every 6 hours |
| `run_observe.bat` | `app.observe_imerg`: fills any missing IMERG days from the last 30 | daily |

On Windows, register both as hidden scheduled tasks (they run on battery and catch up after sleep):

```powershell
powershell -ExecutionPolicy Bypass -File backend\register_tasks.ps1
```

Elsewhere, cron the same modules, e.g. `0 */6 * * * cd /path/to/backend && .venv/bin/python -m app.predict`.
Each job appends to `backend/ingest.log` / `backend/observe.log`.

## API

| Endpoint | Returns |
| --- | --- |
| `GET /api/forecast/area` | the grid as GeoJSON, each cell with chance and mm for every date (one request feeds the whole map) |
| `GET /api/forecast/point?lat&lon` | every day for the cell nearest a point (404 outside the grid) |
| `GET /api/forecast/nearby?lat&lon&day&radius_km` | cells within a radius, nearest first, with distance and compass direction |
| `GET /api/health` | `{"ok": true}` |

All endpoints read only the newest run of `DISPLAY_MODEL` (`lgbm_v1` by default; set it to
`ecmwf_ifs025` to show the raw ensemble instead).

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest                       # API tests run against the database and skip if it's down

cd frontend
npm run typecheck            # strict TypeScript; npm run build also runs it
```

## Layout

```
db/001_init.sql              grid_cell, forecast_daily, observation_daily
db/002_hindcast.sql          forecast_hindcast (past forecasts for training)
backend/app/main.py          API
backend/app/predict.py       live ML probabilities -> forecast_daily (model lgbm_v1)
backend/app/ingest.py        raw ensemble probabilities -> forecast_daily (model ecmwf_ifs025)
backend/app/observe_imerg.py NASA IMERG daily rainfall -> observation_daily
backend/app/backfill_forecasts.py  past ECMWF runs -> forecast_hindcast
backend/app/openmeteo.py     shared Open-Meteo request and daily-total helpers
backend/app/migrate.py       applies db/*.sql
backend/app/seed_grid.py     builds the grid from BBOX and GRID_STEP
backend/ml/train_model.py    features, training, evaluation
backend/tests/               pytest suite
frontend/src/                React + TypeScript app (Leaflet map, Recharts chart, Tailwind v4)
frontend/src/types.ts        API response types, mirroring backend/app/main.py
```

## What "chance of rain" means here

The probability that at least `RAIN_THRESHOLD_MM` (default 1 mm) falls in that grid square during
a UTC day (05:30 to 05:30 IST), as predicted by the model from the ECMWF forecast for the square and
its neighbours, the previous run, and the lead time. ECMWF is ~25 km resolution, so a grid finer
than 0.25 degrees only interpolates. The model was trained on June to September, so treat other
months with care.

Keep `TIMEZONE=GMT`: IMERG days are UTC days, and the training pairs only line up if the
forecasts use the same days.

## Ideas

- **Nowcast (0-6 h):** a ConvLSTM/U-Net on radar or satellite frames, once radar data is available.
- **Ship:** containerize the API and serve the built frontend behind it.
