# Rain risk: localized rain-probability maps

Ensemble weather forecasts -> rain probability per grid cell -> map with "what's the chance around me".

```
Open-Meteo ensemble API --> ingest.py --> PostGIS --> FastAPI --> React + Leaflet
(51 ECMWF members)         (pandas)       (grid_cell,  (/api/...)   (map, nearby list,
                                           forecast_daily)           7-day chart)
```

## Run it

Needs Docker, Python 3.11+, Node 18+.

```bash
# 1. database (PostGIS)
docker compose up -d

# 2. backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # then edit BBOX to your region
python -m app.seed_grid                                 # create the grid cells
python -m app.ingest                                    # fetch forecasts (takes a minute)
uvicorn app.main:app --reload                           # http://localhost:8000/docs

# 3. frontend (new terminal)
cd frontend
npm install
npm run dev                                             # http://localhost:5173
```

Click the map to pick a spot. The side panel shows the chance of rain there, the areas
within 10/25/50 km with direction and distance, and the 7-day outlook.

If the DB schema changes, reset with `docker compose down -v && docker compose up -d`
(init.sql only runs when the volume is first created).

## Check the API by hand

Before trusting the ingest, look at what Open-Meteo actually returns:

```bash
curl "https://ensemble-api.open-meteo.com/v1/ensemble?latitude=13&longitude=77.5&hourly=precipitation&models=ecmwf_ifs025&forecast_days=2"
```

You should see `precipitation` plus one `precipitation_memberNN` key per ensemble member.
`ingest.summarize()` treats every key starting with `precipitation` as a member.

## Keep it fresh

Ingest every 6 hours. Cron example:

```
0 */6 * * *  cd /path/to/rain-risk/backend && .venv/bin/python -m app.ingest
```

Every run is stored (see `forecast_daily.fetched_at`); the API reads the `forecast_latest` view.
Open-Meteo only retains individual ensemble members for a few days, so **this archive is your
training data**. Start collecting now, even before you build the ML step.

## Layout

```
db/init.sql               PostGIS schema, forecast_latest view, observation table
backend/app/main.py       API: /api/meta, /api/forecast/{map,nearby,point}
backend/app/ingest.py     fetch ensemble -> per-cell daily probabilities
backend/app/seed_grid.py  build the grid from BBOX and GRID_STEP
backend/ml/calibrate.py   phase 2: isotonic calibration + Brier score
frontend/src/             React app (Leaflet map, Recharts chart, Tailwind v4)
```

## What "chance of rain" means here

`p_rain` = share of the 51 ensemble members whose daily total is >= `RAIN_THRESHOLD_MM` (default 1 mm)
in that grid cell. It is raw, not calibrated. The ensemble is ~25 km resolution, so a grid finer
than 0.25 degrees only interpolates; it does not add real local detail. That comes from phase 2 and 3.

## Roadmap

1. **Now:** working map from raw ensemble probabilities.
2. **Calibrate:** load rainfall observations into `observation_daily` (rain gauges, IMD gridded data,
   or satellite estimates such as GPM IMERG), then run `ml/calibrate.py`. Apply the saved calibrator in the API.
3. **Downscale:** LightGBM/XGBoost with inputs like ensemble mean/spread, elevation, distance to coast,
   month, and lead time, trained on your archive against observations.
4. **Nowcast (0-6 h):** PyTorch model (ConvLSTM/U-Net) on radar or satellite frames. Only worth it
   once steps 1 to 3 work and you have radar data access.
5. **Ship:** Dockerize the API, add caching (forecasts only change every few hours), and show
   calibrated probabilities with an honest "lower confidence" note for days 5 to 7.
