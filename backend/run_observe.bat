@echo off
rem Daily IMERG observations; fills any missing recent days.
cd /d "%~dp0"
echo ===== %date% %time% ===== >> observe.log
.venv\Scripts\python.exe -m app.observe_imerg >> observe.log 2>&1
