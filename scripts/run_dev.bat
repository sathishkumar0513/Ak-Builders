@echo off
REM Starts Django (port 8000) and React (port 5173) in two windows.
REM After an update it first installs any new packages and applies database changes (migrations),
REM so nothing has to be done by hand. When nothing changed these steps take a few seconds.
start "AK Builders - Backend" cmd /k "cd /d %~dp0..\backend && venv\Scripts\activate && pip install -q --disable-pip-version-check -r requirements.txt && python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000"
start "AK Builders - Frontend" cmd /k "cd /d %~dp0..\frontend && npm install --no-audit --no-fund --loglevel=error && npm run dev"
timeout /t 12 >nul
start http://localhost:5173
