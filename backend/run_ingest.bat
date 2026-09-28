@echo off
cd /d C:\Users\Goku\works\rain-risk\backend
.venv\Scripts\python.exe -m app.ingest >> ingest.log 2>&1
