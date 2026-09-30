@echo off
cd /d C:\Users\Goku\works\rain-risk\backend
echo ===== %date% %time% ===== >> ingest.log
.venv\Scripts\python.exe -m app.ingest >> ingest.log 2>&1
.venv\Scripts\python.exe -m app.predict >> ingest.log 2>&1
