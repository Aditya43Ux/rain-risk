@echo off
cd /d C:\Users\Goku\works\rain-risk\backend
echo ===== %date% %time% ===== >> observe.log
.venv\Scripts\pythonw.exe -m app.observe_imerg >> observe.log 2>&1
