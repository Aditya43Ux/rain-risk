@echo off
rem Forecast refresh: raw ensemble archive, then live ML probabilities for the map.
cd /d "%~dp0"
echo ===== %date% %time% ===== >> ingest.log
.venv\Scripts\python.exe -m app.ingest >> ingest.log 2>&1
.venv\Scripts\python.exe -m app.predict >> ingest.log 2>&1
